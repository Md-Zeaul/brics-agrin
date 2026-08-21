/// What the farmer has already done to this field, as S1 collects it.
///
/// Two facts no satellite can supply: that a dose of nitrogen has already gone
/// on, and that water is already in the ground. Without them M1 will confidently
/// recommend both a second time — soil-water reanalysis lags a fresh irrigation
/// by days, and nothing at all reveals a fertiliser bag.
///
/// Every field here is optional, and each one that is answered buys something
/// on its own:
///
///   a date alone    the next dose is held back until the crop can use it
///   + a product     a non-nitrogen product stops triggering that hold, and
///                   phosphorus advice is withheld when phosphorus went on
///   + a quantity    the season's remaining nitrogen becomes arithmetic
///                   instead of a general rate
///
/// Nothing forces the farmer up that ladder. `notSure` is a real answer at
/// every rung, and it degrades to the rung below rather than to nothing.
library;

/// The fertiliser products sold to Indian smallholders, in picker order.
///
/// Ids mirror `backend/m1_advisory/products.py` and a backend test asserts the
/// two lists match — the nutrient percentages live there, because the
/// arithmetic does. Nothing here knows what is in a bag; it only knows what to
/// call one.
const List<({String id, String label})> kFertiliserProducts = [
  (id: 'urea', label: 'Urea'),
  (id: 'dap', label: 'DAP'),
  (id: 'npk_12_32_16', label: 'NPK 12:32:16'),
  (id: 'npk_10_26_26', label: 'NPK 10:26:26'),
  (id: 'npk_19_19_19', label: 'NPK 19:19:19'),
  (id: 'ssp', label: 'Single super phosphate'),
  (id: 'mop', label: 'Muriate of potash'),
  (id: 'fym', label: 'Farmyard manure'),
  (id: 'unknown', label: "Don't remember"),
];

/// Products whose quantity cannot be turned into kilograms of nutrient.
///
/// Manure is spread by the trolley and its analysis depends on what the animals
/// ate; an unremembered product has no analysis at all. Asking for bags per acre
/// in either case collects a number that can only be misused, so the field is
/// disabled rather than merely ignored.
const Set<String> kUnquantifiableProducts = {'fym', 'unknown'};

/// Bags per acre, as a picker rather than a text field. A farmer buys in whole
/// and half bags, and the Build Brief's S1 target is almost no typing.
const List<double> kBagOptions = [0.5, 1, 1.5, 2, 3];

class FieldHistory {
  const FieldHistory({
    this.fertilisedOn,
    this.product,
    this.bagsPerAcre,
    this.irrigatedOn,
  });

  final DateTime? fertilisedOn;
  final String? product;
  final double? bagsPerAcre;
  final DateTime? irrigatedOn;

  bool get isEmpty => fertilisedOn == null && irrigatedOn == null;

  static String? _iso(DateTime? date) =>
      date?.toIso8601String().split('T').first;

  String? get lastIrrigationIso => _iso(irrigatedOn);

  /// The log as M0 stores it. Empty when no date was given: an entry with no
  /// date is not a weaker record of an application, it is a record of nothing.
  List<Map<String, dynamic>> get log {
    final date = _iso(fertilisedOn);
    if (date == null) return const [];
    final quantifiable =
        product != null && !kUnquantifiableProducts.contains(product);
    return [
      {
        'date': date,
        if (product != null) 'product': product,
        if (quantifiable && bagsPerAcre != null) 'bagsPerAcre': bagsPerAcre,
      }
    ];
  }

  FieldHistory copyWith({
    DateTime? fertilisedOn,
    String? product,
    double? bagsPerAcre,
    DateTime? irrigatedOn,
    bool clearFertilised = false,
    bool clearIrrigated = false,
  }) =>
      FieldHistory(
        fertilisedOn: clearFertilised ? null : fertilisedOn ?? this.fertilisedOn,
        product: clearFertilised ? null : product ?? this.product,
        // Cleared alongside the product, because "2 bags" is meaningless once
        // the thing being counted is gone.
        bagsPerAcre: clearFertilised
            ? null
            : (product != null && product != this.product)
                ? bagsPerAcre
                : bagsPerAcre ?? this.bagsPerAcre,
        irrigatedOn: clearIrrigated ? null : irrigatedOn ?? this.irrigatedOn,
      );
}
