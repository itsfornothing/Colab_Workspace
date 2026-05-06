// collaboration.dart
import 'package:flutter/material.dart';
import 'package:mobile_app/widgets/CollaborativeCanvas.dart';

class CollaborationOnboarding extends StatelessWidget {  // Changed to Stateless
  const CollaborationOnboarding({super.key});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24),
        child: Column(
          children: [
            const SizedBox(height: 40),
            const CollaborativeCanvas(),
            const SizedBox(height: 32),
            const Text(
              'Real-time Collaboration',
              style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 12),
            const Text(
              'Experience the fluidity of Notion-like document co-authoring combined with the immediacy of Slack-like contextual conversations.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 16, height: 1.5),
            ),
            const SizedBox(height: 40),
          ],
        ),
      ),
    );
  }
}