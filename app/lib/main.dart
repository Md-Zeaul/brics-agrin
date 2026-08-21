/// AgriSetu — the app shell.
///
/// Boots straight into S1 unless a cached profile exists, in which case the
/// farmer lands on S2 with no network call at all.
///
/// S1 and S2 are constructed directly because they carry the field repository
/// and the profile that came out of it. S3–S10 are named routes, so any screen
/// can reach any other without knowing who built it.
library;

import 'package:flutter/material.dart';

import 'core/l10n/app_language.dart';
import 'core/l10n/language_scope.dart';
import 'core/routes.dart';
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
  final LanguageController _language = LanguageController(AppLanguage.hindi);

  @override
  void dispose() {
    _repository.dispose();
    _language.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return LanguageScope(
      controller: _language,
      child: MaterialApp(
        title: 'AgriSetu',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF2E7D32)),
          useMaterial3: true,
        ),
        routes: Routes.table,
        home: _Bootstrap(repository: _repository),
      ),
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
          result: FieldProfileResult(
            profile: cached,
            origin: ProfileOrigin.restored,
          ),
          repository: repository,
        );
      },
    );
  }
}
