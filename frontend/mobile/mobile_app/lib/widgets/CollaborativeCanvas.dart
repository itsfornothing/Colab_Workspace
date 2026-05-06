import 'package:flutter/material.dart';
import 'dart:ui';

class CollaborativeCanvas extends StatelessWidget {
  // ... (same reusable widget as before - keeping it short here)
  final double width;
  final double height;
  final String message;
  final String editorName;
  final String mainAvatarUrl;
  final List<String> liveAvatars;
  final String? liveText;

  const CollaborativeCanvas({
    super.key,
    this.width = 340,
    this.height = 340,
    this.message = "Can we update the architectural flow in the second section?",
    this.editorName = "Alex",
    this.mainAvatarUrl = "https://lh3.googleusercontent.com/aida-public/AB6AXuC6SR5mPWDZZIIezVvBILEqlQlP7a8CWrOb2qTB1MMe2Y6DXNpt2VUF-Z6QfXXjkWuB2SWDn9sN9QHGhrGunhr1kYGUJnF0pqTIGZ5WBs-cO2bFK-0-PUVz0_C0gnTmI3Uy6fmjY5--J7jCwjA8-1fyOYNX8fuT7QRu3Ry7xaNHno6sU3zR68SpsWFd-HbqymXsLIAk-hUgkRhiyBZSG9qmZft22N-4saHOhMVFggjhIZvjHayJml8vyPC8vafYUii2zPmMaw6nOjUR",
    this.liveAvatars = const [
      "https://lh3.googleusercontent.com/aida-public/AB6AXuCXFPT_w-UC8NC1DJGDSl9H71es6KLsbnzfgtzdPXuLqifxTyMCDIzAvhIoOGd0nA-d34e7Ux5PB163tof_fs2-5KsU-RCeEFy4uTlzoLeWUnN_X8sn2hYgVovrPhg8no7BB9vf0hFZ-t5YfHBJut7wRnpZkIKNB9ici9mZcZoG25XLN8v8v-Y02kJkv_BuN3sHgvU23JiQr-qWiePcLwXlYt5TeFdIK0HDP46voyqYgC3IJMTpX4rYgDYGXzFLPLn3qTWUg8fG0TGY",
      "https://lh3.googleusercontent.com/aida-public/AB6AXuCLmgmqoW2E9oWuKg7tcpXWr9MH6e6aOBPkRgtnWtYjB3Gk1Rd85eFQHCbq9KTAKV6fY8XsV84I6c9n64braKznJODp98GZCdMfGkWtht3aliFapKRHaLzsYM7vWsgA-F7D_u7rtNEQgcLnpL4roj7DwvZCv_2CHk99xoY24VqS4LBZ_bv2e6LXzHznuWCriN7vG-32EktpQzkV_FXGvO3sECaYAdWd6o1Ei_t03AX-yMKLnNnXm6GOyxXsp1c4FuTLZb1h37X4DYZt",
    ],
    this.liveText = "LIVE NOW",
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      height: height,
      child: Stack(
        children: [
          // Main Canvas
          Padding(
            padding: const EdgeInsets.all(16),
            child: Container(
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(20),
                boxShadow: [
                  BoxShadow(
                    color: const Color(0xFF4648D4).withOpacity(0.06),
                    blurRadius: 40,
                    offset: const Offset(0, 20),
                  ),
                ],
              ),
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(height: 16, width: 220, decoration: BoxDecoration(color: const Color(0xFFF0F2F8), borderRadius: BorderRadius.circular(999))),
                  const SizedBox(height: 12),
                  Container(height: 16, width: 140, decoration: BoxDecoration(color: const Color(0xFFF0F2F8), borderRadius: BorderRadius.circular(999))),
                  const Spacer(),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 42,
                        height: 42,
                        decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: Colors.white, width: 3)),
                        child: ClipOval(child: Image.network(mainAvatarUrl, fit: BoxFit.cover)),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Container(
                          padding: const EdgeInsets.all(14),
                          decoration: const BoxDecoration(
                            color: Color(0xFFF0F2F8),
                            borderRadius: BorderRadius.only(
                              topLeft: Radius.circular(4),
                              topRight: Radius.circular(20),
                              bottomLeft: Radius.circular(20),
                              bottomRight: Radius.circular(20),
                            ),
                          ),
                          child: Text(message, style: const TextStyle(fontSize: 13, height: 1.4, color: Color(0xFF4A4A5C))),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),

          // Cursor
          Positioned(
            top: height * 0.42,
            left: width * 0.32,
            child: Row(
              children: [
                const Icon(Icons.near_me, color: Color(0xFF4648D4), size: 32),
                const SizedBox(width: 6),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(30),
                    boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.08), blurRadius: 12, offset: const Offset(0, 4))],
                  ),
                  child: Text("$editorName editing...", style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Color(0xFF4648D4))),
                ),
              ],
            ),
          ),

          // Live Panel
          Positioned(
            right: -8,
            top: 70,
            child: Container(
              width: 138,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.85),
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: Colors.white.withOpacity(0.5)),
                boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.12), blurRadius: 20, offset: const Offset(0, 8))],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(width: 9, height: 9, decoration: const BoxDecoration(color: Colors.green, shape: BoxShape.circle)),
                      const SizedBox(width: 6),
                      Text(liveText!.toUpperCase(), style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, letterSpacing: 1.2, color: Color(0xFF6B7280))),
                    ],
                  ),
                  const SizedBox(height: 12),
                  SizedBox(
                    height: 34,
                    child: Stack(
                      children: [
                        for (int i = 0; i < liveAvatars.length; i++)
                          Positioned(left: i * 26.0, child: CircleAvatar(radius: 17, backgroundImage: NetworkImage(liveAvatars[i]))),
                        Positioned(
                          left: liveAvatars.length * 26.0,
                          child: CircleAvatar(
                            radius: 17,
                            backgroundColor: const Color(0xFF4648D4),
                            child: const Text("+4", style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.white)),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ==================== Usage Example ====================

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8F9FF),
      appBar: AppBar(title: const Text("Design Collaboration")),
      body: SingleChildScrollView(
        child: Column(
          children: [
            const SizedBox(height: 40),

            // Your Collaborative Canvas Widget
            const CollaborativeCanvas(),

            const SizedBox(height: 40),

            // You can add more widgets below
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    "Team Activity",
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 16),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: const Text("More content can go here..."),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 60),
          ],
        ),
      ),
    );
  }
}