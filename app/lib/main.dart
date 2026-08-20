/// AgriSetu — M0 field intelligence.
///
/// Boots straight into S1 unless a cached profile exists, in which case the
/// farmer lands on S2 with no network call at all.
library;

import 'package:flutter/material.dart';

import 'features/field/data/field_repository.dart';
import 'features/field/presentation/home_screen.dart';
import 'features/field/presentation/onboarding_screen.dart';

void main() => runApp(const AgriSetuApp());

class AgriSetuApp extends StatefulWidget {
  const AgriSetuApp({super.key});

  @override
  State<AgriSetuApp> createState() => _AgriSetuAppState();
}

class _AgriSetuAppState extends State<AgriSetuApp> {
  final FieldRepository _repository = FieldRepository();

  @override
  void dispose() {
    _repository.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AgriSetu',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF2E7D32)),
        useMaterial3: true,
      ),
      home: _Bootstrap(repository: _repository),
    );
  }
}

/// Offline-first entry: paint from cache before touching the network.
class _Bootstrap extends StatelessWidget {
  const _Bootstrap({required this.repository});

  final FieldRepository repository;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder(
      future: repository.cachedProfile(),
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }

        final cached = snapshot.data;
        if (cached == null) {
          return OnboardingScreen(repository: repository);
        }

        return HomeScreen(
          result: FieldProfileResult(profile: cached, fromCache: true),
          repository: repository,
        );
      },
    );
  }
}
