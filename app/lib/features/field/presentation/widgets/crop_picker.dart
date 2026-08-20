/// Crop selection for S1.
///
/// A searchable field over the registry, matching in any of its languages, with
/// free text accepted for anything unlisted. The Build Brief wants almost no
/// typing, so this behaves as a tap-to-pick list until the farmer starts typing.
library;

import 'package:flutter/material.dart';

import '../../domain/crop.dart';

class CropPicker extends StatefulWidget {
  const CropPicker({
    super.key,
    required this.registry,
    required this.selected,
    required this.language,
    required this.onChanged,
  });

  final CropRegistry registry;
  final Crop? selected;
  final String language;
  final ValueChanged<Crop> onChanged;

  @override
  State<CropPicker> createState() => _CropPickerState();
}

class _CropPickerState extends State<CropPicker> {
  late final TextEditingController _controller;
  late final FocusNode _focus;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: _label);
    _focus = FocusNode()..addListener(_onFocusChange);
  }

  @override
  void didUpdateWidget(CropPicker old) {
    super.didUpdateWidget(old);
    // The registry loads after the first frame and the language can toggle, so
    // the shown label has to follow the selection rather than being captured
    // once. Never fight the farmer mid-edit.
    if (!_focus.hasFocus && _controller.text != _label) {
      _controller.text = _label;
    }
  }

  @override
  void dispose() {
    _focus.removeListener(_onFocusChange);
    _focus.dispose();
    _controller.dispose();
    super.dispose();
  }

  String get _label => widget.selected?.label(widget.language) ?? '';

  /// Selecting the text on focus means the first keystroke replaces the current
  /// crop instead of appending to it — "गेहूँbajra" matches nothing.
  void _onFocusChange() {
    if (!_focus.hasFocus) return;
    _controller.selection = TextSelection(
      baseOffset: 0,
      extentOffset: _controller.text.length,
    );
  }

  /// The whole registry when the farmer has not typed anything of their own.
  ///
  /// The field is pre-filled with the current crop, so filtering by its text
  /// would offer exactly one option — the crop already chosen. Tapping the box
  /// has to show the list, or the other crops are unreachable without first
  /// clearing it by hand.
  bool _isUntouched(String text) =>
      text.trim().isEmpty || text == _label;

  @override
  Widget build(BuildContext context) {
    return Autocomplete<Crop>(
      textEditingController: _controller,
      focusNode: _focus,
      displayStringForOption: (crop) => crop.label(widget.language),
      optionsBuilder: (value) {
        if (_isUntouched(value.text)) return widget.registry.crops;

        final matches = widget.registry.search(value.text);
        // Anything the registry does not know is still a real crop.
        if (matches.isEmpty) return [Crop.other(value.text.trim())];
        return matches;
      },
      onSelected: widget.onChanged,
      fieldViewBuilder: (context, controller, focusNode, onSubmit) {
        return TextFormField(
          controller: controller,
          focusNode: focusNode,
          decoration: InputDecoration(
            labelText: 'Crop',
            border: const OutlineInputBorder(),
            suffixIcon: IconButton(
              icon: const Icon(Icons.arrow_drop_down),
              tooltip: 'Show all crops',
              onPressed: () {
                // Opening the list is what the arrow promises; focusing the
                // field with untouched text is what actually opens it.
                if (focusNode.hasFocus) {
                  focusNode.unfocus();
                } else {
                  controller.text = _label;
                  focusNode.requestFocus();
                }
              },
            ),
            helperText:
                widget.selected?.isOther ?? false ? 'Not in our list' : null,
          ),
          // Typing something unlisted and moving on must still register.
          onFieldSubmitted: (text) {
            final trimmed = text.trim();
            if (trimmed.isEmpty) return;
            final match = widget.registry.search(trimmed);
            widget.onChanged(
              match.isNotEmpty ? match.first : Crop.other(trimmed),
            );
            onSubmit();
          },
        );
      },
      optionsViewBuilder: (context, onSelected, options) {
        return Align(
          alignment: Alignment.topLeft,
          child: Material(
            elevation: 4,
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 260, maxWidth: 320),
              child: ListView.builder(
                shrinkWrap: true,
                padding: EdgeInsets.zero,
                itemCount: options.length,
                itemBuilder: (context, index) {
                  final crop = options.elementAt(index);
                  final chosen = crop == widget.selected;
                  return ListTile(
                    dense: true,
                    selected: chosen,
                    title: Text(crop.label(widget.language)),
                    subtitle: crop.isOther
                        ? const Text('Use what you typed')
                        : (crop.category == null ? null : Text(crop.category!)),
                    trailing: chosen ? const Icon(Icons.check, size: 18) : null,
                    onTap: () => onSelected(crop),
                  );
                },
              ),
            ),
          ),
        );
      },
    );
  }
}
