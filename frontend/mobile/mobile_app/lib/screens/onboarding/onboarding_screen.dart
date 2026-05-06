// onboarding_screen.dart
import 'package:flutter/material.dart';
import 'package:smooth_page_indicator/smooth_page_indicator.dart';
import 'package:mobile_app/screens/onboarding/collaboration.dart';
import 'package:mobile_app/screens/onboarding/communication.dart';
import 'package:mobile_app/screens/onboarding/workspace.dart';
import 'package:mobile_app/screens/onboarding/welcome.dart';

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final PageController _pageController = PageController();
  int currentPage = 0;

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  void _goToNextPage() {
    if (currentPage < 3) {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 400),
        curve: Curves.easeInOut,
      );
    } else {
      // Finish onboarding - go to main app
      Navigator.of(context).pushReplacementNamed('/main'); // or your TabsScreen
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Theme.of(context).colorScheme.surface,
      body: Stack(
        children: [
          PageView(
            controller: _pageController,
            onPageChanged: (index) {
              setState(() => currentPage = index);
            },
            children: const [
              WelcomeOnboardingPage(),
              CollaborationOnboarding(),
              CommunicationOnboarding(),
              WorkspaceOnboarding(),
            ],
          ),

          // Page Indicator
          Positioned(
            bottom: 40,
            left: 0,
            right: 0,
            child: Center(
              child: SmoothPageIndicator(
                controller: _pageController,
                count: 4,
                effect: ExpandingDotsEffect(
                  activeDotColor: Theme.of(context).colorScheme.primary,
                  dotColor: Colors.grey.shade300,
                  dotHeight: 8,
                  dotWidth: 8,
                  spacing: 6,
                ),
              ),
            ),
          ),

          // Next / Skip Button
          Positioned(
            bottom: 80,
            left: 24,
            right: 24,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                TextButton(
                  onPressed: () => Navigator.of(context).pushReplacementNamed('/main'),
                  child: const Text("Skip"),
                ),
                ElevatedButton.icon(
                  onPressed: _goToNextPage,
                  icon: const Icon(Icons.arrow_forward),
                  label: Text(currentPage == 3 ? "Get Started" : "Next"),
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}