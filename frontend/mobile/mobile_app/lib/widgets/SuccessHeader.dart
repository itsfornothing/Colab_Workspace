import 'package:flutter/material.dart';
import 'dart:ui';

class SuccessHeader extends StatelessWidget {
  final double width;
  final String title;
  final String imageUrl;

  const SuccessHeader({
    super.key,
    this.width = double.infinity,
    this.title = "Ready to go",
    this.imageUrl = "https://lh3.googleusercontent.com/aida-public/AB6AXuAE7lia5ELhWCdAKMLAYhhwqcsYv9bDDQ5Ee9c0ySxIvTN_kyTG0nZ3grwbQfrhhoUB-JiY4SFtvxVmrjK4cavjSuVvTdSzKUPrEb37rcV-soCoHDAEXTeXSmccFT6hYkSiCRHbXM6h5pBXforQDVVud5OfQtLD0FDNKLx5UL1U32EKUfWo6-6_Vm5Lk5g8Kbu2siLmyJmbm-GydkcK2FImmueJAnZ4lCbNCJ9yaenCvYbCrMnWDsXw0dzl4vkoePsNBy8XVK20qhrL",
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        const SizedBox(height: 16), // mt-4 equivalent
        Center(
          child: SizedBox(
            width: width > 0 && width < double.infinity ? width : 340,
            child: AspectRatio(
              aspectRatio: 1,
              child: Stack(
                children: [
                  // Main Image Container
                  ClipRRect(
                    borderRadius: BorderRadius.circular(20),
                    child: Image.network(
                      imageUrl,
                      fit: BoxFit.cover,
                      width: double.infinity,
                      height: double.infinity,
                    ),
                  ),

                  // Gradient Overlay
                  Container(
                    decoration: const BoxDecoration(
                      borderRadius: BorderRadius.all(Radius.circular(20)),
                      gradient: LinearGradient(
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                        colors: [
                          Colors.transparent,
                          Color.fromRGBO(70, 72, 212, 0.25),
                        ],
                      ),
                    ),
                  ),

                  // Glassmorphism Badge
                  Positioned(
                    bottom: 20,
                    right: 20,
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(16),
                      child: BackdropFilter(
                        filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 10,
                          ),
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.85),
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(
                              color: Colors.white.withOpacity(0.6),
                            ),
                            boxShadow: [
                              BoxShadow(
                                color: Colors.black.withOpacity(0.1),
                                blurRadius: 20,
                                offset: const Offset(0, 8),
                              ),
                            ],
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(
                                Icons.check_circle,
                                color: Color(0xFF4648D4),
                                size: 22,
                              ),
                              const SizedBox(width: 8),
                              Text(
                                title,
                                style: const TextStyle(
                                  fontSize: 15,
                                  fontWeight: FontWeight.bold,
                                  color: Color(0xFF1F1F2C),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(height: 32), // mb-8 equivalent
      ],
    );
  }
}