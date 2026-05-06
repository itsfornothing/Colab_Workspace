import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class WelcomeOnboardingPage extends StatelessWidget {
  const WelcomeOnboardingPage({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Spacer(),
          Image.asset('assets/logo.png', width: 140, height: 140), // Fix path
          const SizedBox(height: 32),
          Text(
            'Welcome To',
            style: theme.textTheme.titleLarge?.copyWith(
              color: theme.colorScheme.onSurface.withOpacity(0.8),
            ),
          ),
          Text(
            'Synthesis Flux',
            style: GoogleFonts.lato(
              fontSize: 38,
              fontWeight: FontWeight.bold,
              color: theme.colorScheme.primary,
            ),
          ),
          const SizedBox(height: 16),
          const Text(
            'Collaborate without boundaries',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 12),
          const Text(
            'Experience a workspace where documents, chat, and live interaction converge into a single editorial flow.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 16, height: 1.5),
          ),
          const Spacer(flex: 2),
        ],
      ),
    );
  }
}