/// The ten screens, named once.
///
/// The Build Brief numbers the screens S1–S10 and every conversation about this
/// build uses those numbers, so the constants keep them rather than inventing a
/// second vocabulary. S1 and S2 are pushed directly because they carry
/// constructor arguments; the rest are reachable by name from anywhere.
library;

import 'package:flutter/widgets.dart';

import '../features/command_center/presentation/command_center_screen.dart';
import '../features/command_center/presentation/network_screen.dart';
import '../features/command_center/presentation/region_detail_screen.dart';
import '../features/command_center/presentation/scenario_screen.dart';
import '../features/diagnosis/presentation/diagnosis_screen.dart';
import '../features/diagnosis/presentation/scan_screen.dart';
import '../features/planner/presentation/planner_screen.dart';
import '../features/planner/presentation/what_if_screen.dart';

class Routes {
  const Routes._();

  // Farmer side.
  static const String onboarding = '/s1';      // M0 — field capture
  static const String home = '/s2';            // M0 + M1 — daily advisory
  static const String scan = '/s3';            // M2 — camera
  static const String diagnosis = '/s4';       // M2 — result
  static const String planner = '/s5';         // M3 + M4 — ranked crops
  static const String whatIf = '/s6';          // M8 — sliders

  // Command Center.
  static const String commandCenter = '/s7';   // M5 — risk map
  static const String regionDetail = '/s8';    // M5 — drill-down
  static const String scenario = '/s9';        // M6 — national scenario
  static const String network = '/s10';        // M7 — BRICS nodes

  /// The routes MaterialApp registers. Lives here rather than in `main.dart` so
  /// a widget test navigates through the same table the app does — a screen
  /// that exists but was never registered then fails a test instead of only
  /// failing on demo day.
  static Map<String, WidgetBuilder> get table => {
        scan: (_) => const ScanScreen(),
        diagnosis: (_) => const DiagnosisScreen(),
        planner: (_) => const PlannerScreen(),
        whatIf: (_) => const WhatIfScreen(),
        commandCenter: (_) => const CommandCenterScreen(),
        regionDetail: (_) => const RegionDetailScreen(),
        scenario: (_) => const ScenarioScreen(),
        network: (_) => const NetworkScreen(),
      };
}
