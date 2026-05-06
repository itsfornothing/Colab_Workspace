import 'package:flutter/material.dart';
import 'package:mobile_app/widgets/VideoCallCollaboration.dart';


class CommunicationOnboarding extends StatelessWidget {
  const CommunicationOnboarding({super.key});

  
  @override
  Widget build(BuildContext context) {

    return SingleChildScrollView(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24),
        child: Column(
          children: [
              const SizedBox(height: 40),
               const VideoCallCollaboration(width: 300),
               const SizedBox(height: 32),
            Text(
                    'Unified Communication',
                    style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold),
              textAlign: TextAlign.center,
                  ),
            SizedBox(height: 8),
                  Text('Connect your workspace with seamless Zoom integration. Organize team chats into focused channels and transition from text to video in a single tap.',
                   textAlign: TextAlign.center,
              style: TextStyle(fontSize: 16, height: 1.5),
                  ),
          const SizedBox(height: 40),
           
           
        ]),
      ),
    );
  }
}
