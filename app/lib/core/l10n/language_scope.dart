/// Runtime language switching, available to every screen.
///
/// S10's demo beat — "same app, another nation" — is a language change that has
/// to repaint the whole tree, so the active language is an inherited notifier
/// rather than a parameter threaded down through ten screens.
///
/// Not persisted: the demo is one continuous session, and a language that
/// survives a reload would silently start the next rehearsal in Portuguese.
library;

import 'package:flutter/widgets.dart';

import 'app_language.dart';
import 'strings.dart';

class LanguageController extends ChangeNotifier {
  LanguageController([this._language = AppLanguage.hindi]);

  AppLanguage _language;
  AppLanguage get language => _language;

  AppStrings get strings => AppStrings(_language);

  void switchTo(AppLanguage language) {
    if (language == _language) return;
    _language = language;
    notifyListeners();
  }
}

class LanguageScope extends InheritedNotifier<LanguageController> {
  const LanguageScope({
    super.key,
    required LanguageController controller,
    required super.child,
  }) : super(notifier: controller);

  /// The controller, or null outside a scope.
  ///
  /// Nullable on purpose. Widget tests pump single screens without an app
  /// wrapper, and a screen that throws when it cannot find the scope would
  /// make every one of those tests depend on chrome it is not testing.
  static LanguageController? maybeOf(BuildContext context) {
    return context
        .dependOnInheritedWidgetOfExactType<LanguageScope>()
        ?.notifier;
  }

  /// Strings for the active language, falling back to English outside a scope.
  static AppStrings stringsOf(BuildContext context) {
    return maybeOf(context)?.strings ?? const AppStrings(AppLanguage.english);
  }

  static AppLanguage languageOf(BuildContext context) =>
      maybeOf(context)?.language ?? AppLanguage.english;
}
