import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppColors {
  // Primary
  static const primary = Color(0xFF6366F1);
  static const primaryDark = Color(0xFF818CF8);

  // Backgrounds
  static const bgBaseLight = Color(0xFFF8FAFC);
  static const bgBaseDark = Color(0xFF060E20);
  static const bgPanelLight = Color(0xFFF1F5F9);
  static const bgPanelDark = Color(0xFF091328);

  // Text
  static const textHeadlineLight = Color(0xFF0F172A);
  static const textHeadlineDark = Color(0xFFDEE5FF);
  static const textBodyLight = Color(0xFF475569);
  static const textBodyDark = Color(0xFFA3AAC4);
  static const textHintLight = Color(0xFF94A3B8);
  static const textHintDark = Color(0xFF5B6278);

  // Borders
  static const borderLight = Color(0xFFE2E8F0);
  static const borderDark = Color(0xFF1E293B);

  // Status
  static const success = Color(0xFF10B981);
  static const successDark = Color(0xFF34D399);
  static const danger = Color(0xFFEF4444);
  static const dangerDark = Color(0xFFF87171);
}

class AppTheme {
  static ThemeData light() {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorScheme: const ColorScheme.light(
        primary: AppColors.primary,
        surface: AppColors.bgBaseLight,
        onSurface: AppColors.textHeadlineLight,
        outline: AppColors.borderLight,
        error: AppColors.danger,
      ),
      scaffoldBackgroundColor: AppColors.bgBaseLight,
      textTheme: GoogleFonts.interTextTheme().copyWith(
        displayLarge: GoogleFonts.inter(
            fontSize: 24, fontWeight: FontWeight.w700, color: AppColors.textHeadlineLight),
        displayMedium: GoogleFonts.inter(
            fontSize: 20, fontWeight: FontWeight.w600, color: AppColors.textHeadlineLight),
        bodyLarge: GoogleFonts.inter(
            fontSize: 15, fontWeight: FontWeight.w400, color: AppColors.textBodyLight),
        bodySmall: GoogleFonts.inter(
            fontSize: 12, fontWeight: FontWeight.w400, color: AppColors.textHintLight),
        labelLarge: GoogleFonts.inter(
            fontSize: 15, fontWeight: FontWeight.w600, color: Colors.white),
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        color: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        shadowColor: Colors.black.withOpacity(0.06),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.bgPanelLight,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.borderLight),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.borderLight),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.primary, width: 2),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          minimumSize: const Size(double.infinity, 52),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          textStyle: GoogleFonts.inter(fontSize: 15, fontWeight: FontWeight.w600),
        ),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: Colors.white,
        selectedItemColor: AppColors.primary,
        unselectedItemColor: AppColors.textHintLight,
        type: BottomNavigationBarType.fixed,
        elevation: 8,
      ),
    );
  }

  static ThemeData dark() {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: const ColorScheme.dark(
        primary: AppColors.primaryDark,
        surface: AppColors.bgBaseDark,
        onSurface: AppColors.textHeadlineDark,
        outline: AppColors.borderDark,
        error: AppColors.dangerDark,
      ),
      scaffoldBackgroundColor: AppColors.bgBaseDark,
      textTheme: GoogleFonts.interTextTheme(ThemeData.dark().textTheme).copyWith(
        displayLarge: GoogleFonts.inter(
            fontSize: 24, fontWeight: FontWeight.w700, color: AppColors.textHeadlineDark),
        displayMedium: GoogleFonts.inter(
            fontSize: 20, fontWeight: FontWeight.w600, color: AppColors.textHeadlineDark),
        bodyLarge: GoogleFonts.inter(
            fontSize: 15, fontWeight: FontWeight.w400, color: AppColors.textBodyDark),
        bodySmall: GoogleFonts.inter(
            fontSize: 12, fontWeight: FontWeight.w400, color: AppColors.textHintDark),
        labelLarge: GoogleFonts.inter(
            fontSize: 15, fontWeight: FontWeight.w600, color: Colors.white),
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        color: AppColors.bgPanelDark,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.bgPanelDark,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.borderDark),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.borderDark),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.primaryDark, width: 2),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.primaryDark,
          foregroundColor: Colors.white,
          minimumSize: const Size(double.infinity, 52),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          textStyle: GoogleFonts.inter(fontSize: 15, fontWeight: FontWeight.w600),
        ),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: AppColors.bgPanelDark,
        selectedItemColor: AppColors.primaryDark,
        unselectedItemColor: AppColors.textHintDark,
        type: BottomNavigationBarType.fixed,
        elevation: 8,
      ),
    );
  }
}
