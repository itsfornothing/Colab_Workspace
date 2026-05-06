import 'package:flutter/material.dart';
import 'dart:ui';

class VideoCallCollaboration extends StatelessWidget {
  final double width;

  const VideoCallCollaboration({
    super.key,
    this.width = 300,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      height: 380,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          // Background Decorative Shape
          Positioned(
            top: -30,
            left: -30,
            child: Container(
              width: 180,
              height: 180,
              decoration: BoxDecoration(
                color: const Color(0xFF4648D4).withOpacity(0.08),
                shape: BoxShape.circle,
              ),
            ),
          ),

          // Main Video Call Card
          Positioned.fill(
            child: Align(
              alignment: Alignment.center,
              child: Container(
                width: width,
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.85),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: Colors.white.withOpacity(0.6)),
                  boxShadow: [
                    BoxShadow(
                      color: const Color(0xFF4648D4).withOpacity(0.08),
                      blurRadius: 40,
                      offset: const Offset(0, 20),
                    ),
                  ],
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(20),
                  child: BackdropFilter(
                    filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        children: [
                          // Video Frame
                          ClipRRect(
                            borderRadius: BorderRadius.circular(14),
                            child: AspectRatio(
                              aspectRatio: 16 / 9,
                              child: Image.network(
                                'https://lh3.googleusercontent.com/aida-public/AB6AXuCJ5GxymxJMRgL_u7cFMjMuhBbwpQ8PMup0jroHuDYcGmwCSByh207NWXoq1UpPEOXt_GnTYS-eGqpR7gnPN0MX-LMDOmI65_OX6h6n_J7aX2mg08IqBT_k3lc9j7i7Udrz-1HzVbQZ5kdyUsm08dl756_honJi2TX4g2wnsQaBTe5GPX9FmaffDkboBTs1o3_CEFpm83-DhUANASrya25WuszejHpWtRESmdl-7a9qAeTYCZWuB5h1DN_bwSIf18Q6GuiYJfyLqYSv',
                                fit: BoxFit.cover,
                              ),
                            ),
                          ),

                          const SizedBox(height: 12),

                          // Bottom Controls
                          Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 8),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                // Action Buttons
                                Row(
                                  children: [
                                    _buildControlButton(Icons.mic, Colors.blue),
                                    const SizedBox(width: 12),
                                    _buildControlButton(Icons.call_end, Colors.red),
                                  ],
                                ),

                                // Participants
                                Row(
                                  children: [
                                    _buildSmallAvatar(Colors.grey[300]!),
                                    _buildSmallAvatar(Colors.grey[400]!),
                                    Container(
                                      width: 24,
                                      height: 24,
                                      decoration: BoxDecoration(
                                        color: const Color(0xFF4648D4),
                                        shape: BoxShape.circle,
                                        border: Border.all(color: Colors.white, width: 2),
                                      ),
                                      child: const Center(
                                        child: Text(
                                          "+3",
                                          style: TextStyle(
                                            color: Colors.white,
                                            fontSize: 10,
                                            fontWeight: FontWeight.bold,
                                          ),
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),

          // "Zoom Live" Badge
          Positioned(
            bottom: 92,
            left: 28,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
              decoration: BoxDecoration(
                color: Colors.black.withOpacity(0.6),
                borderRadius: BorderRadius.circular(4),
              ),
              child: const Text(
                "Zoom Live",
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),

          // Floating Chat Simulation
          Positioned(
            right: -30,
            top: 110,
            child: Transform.rotate(
              angle: 0.08,
              child: Container(
                width: 170,
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: Colors.grey.withOpacity(0.2)),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.1),
                      blurRadius: 20,
                      offset: const Offset(4, 10),
                    ),
                  ],
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 8,
                          height: 8,
                          decoration: const BoxDecoration(
                            color: Color(0xFF4648D4),
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(width: 6),
                        const Text(
                          "#product-launch",
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: Color(0xFF6B7280),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Container(height: 6, width: double.infinity, decoration: BoxDecoration(color: Colors.grey[200], borderRadius: BorderRadius.circular(999))),
                    const SizedBox(height: 8),
                    Container(height: 6, width: 110, decoration: BoxDecoration(color: Colors.grey[200], borderRadius: BorderRadius.circular(999))),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildControlButton(IconData icon, Color color) {
    return Container(
      width: 42,
      height: 42,
      decoration: BoxDecoration(
        color: color,
        shape: BoxShape.circle,
      ),
      child: Icon(icon, color: Colors.white, size: 22),
    );
  }

  Widget _buildSmallAvatar(Color color) {
    return Container(
      width: 26,
      height: 26,
      margin: const EdgeInsets.only(right: 6),
      decoration: BoxDecoration(
        color: color,
        shape: BoxShape.circle,
        border: Border.all(color: Colors.white, width: 2),
      ),
    );
  }
}