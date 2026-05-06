import 'package:flutter/material.dart';
import 'package:mobile_app/widgets/SuccessHeader.dart';


class WorkspaceOnboarding extends StatelessWidget {
  const WorkspaceOnboarding({super.key});

  
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return SingleChildScrollView(
      
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24),
        child:Column( 
          children: [
              const SizedBox(height: 20),
               const SuccessHeader(),
               const SizedBox(height: 32),
            Text(
                    'Your Workspace Awaits',
                    style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold),
              textAlign: TextAlign.center,
                  ),
            const SizedBox(height: 12),
                  Text('Everything is set up. Your creative sanctuary is ready for its first collaborative stroke.',
                  textAlign: TextAlign.center,
              style: TextStyle(fontSize: 16, height: 1.5),
              ),
 const SizedBox(height: 12),

            // Feature Recap Grid
Padding(
  padding: const EdgeInsets.symmetric(horizontal: 20),
  child: GridView.count(
    shrinkWrap: true,
    physics: const NeverScrollableScrollPhysics(),
    crossAxisCount: 2,
    mainAxisSpacing: 16,
    crossAxisSpacing: 16,
    childAspectRatio: 1, // Makes the small cards square
    children: [
      // 1. Full-width Centralized Hub Card (spans 2 columns)
      Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: const Color(0xFFF0F2F8), // surface-container-lowest
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          children: [
            Container(
              height: 52,
              width: 52,
              decoration: BoxDecoration(
                color: const Color(0xFF4648D4).withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(
                Icons.hub,
                color: Color(0xFF4648D4),
                size: 28,
              ),
            ),
            const SizedBox(width: 16),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    "Centralized Hub",
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF1F1F2C),
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    "All tools connected in one flow.",
                    style: TextStyle(
                      fontSize: 14,
                      color: Color(0xFF6B7280),
                      height: 1.3,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),

      // 2. Live Co-Editing Card
      Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: const Color(0xFFF8F9FF), // surface-container
          borderRadius: BorderRadius.circular(20),
        ),
        child: const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Icon(
              Icons.groups,
              color: Color(0xFF4648D4),
              size: 42,
            ),
            Text(
              "Live Co-Editing",
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.bold,
                height: 1.2,
                color: Color(0xFF1F1F2C),
              ),
            ),
          ],
        ),
      ),

      // 3. AI Insights Card
      Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: const Color(0xFFF0F2F8), // surface-container-low
          borderRadius: BorderRadius.circular(20),
        ),
        child: const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Icon(
              Icons.auto_awesome,
              color: Color(0xFF4648D4),
              size: 42,
            ),
            Text(
              "AI Insights",
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.bold,
                height: 1.2,
                color: Color(0xFF1F1F2C),
              ),
            ),
          ],
        ),
      ),
    ],
  ),
),
           
                  SizedBox(height: 12),
      Text(
                    'Already have an account? ',
                    style: TextStyle(
                      color: theme.colorScheme.onSurface.withValues(alpha: 0.7),
                    ),
                  ),
                            const SizedBox(height: 40),

        ]),
      ),
       
    );
  }
}
