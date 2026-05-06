import 'dart:convert';
import 'dart:io';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:http/http.dart' as http;

/// Uploads a file directly to Cloudinary using an unsigned upload preset.
///
/// Cloud name and upload preset are read from the `.env` file:
///   CLOUDINARY_CLOUD_NAME=...
///   CLOUDINARY_UPLOAD_PRESET=...
///
/// Returns the secure URL of the uploaded asset, or null on failure.
class CloudinaryService {
  static String get _cloudName =>
      dotenv.env['CLOUDINARY_CLOUD_NAME'] ?? '';

  static String get _uploadPreset =>
      dotenv.env['CLOUDINARY_UPLOAD_PRESET'] ?? '';

  /// Upload [file] to Cloudinary and return its secure URL.
  /// Pass an optional [resourceType] ('image', 'video', 'raw', or 'auto').
  static Future<String?> upload(
    File file, {
    String resourceType = 'auto',
  }) async {
    if (_cloudName.isEmpty || _uploadPreset.isEmpty) {
      throw StateError(
        'Cloudinary env vars missing. '
        'Set CLOUDINARY_CLOUD_NAME and CLOUDINARY_UPLOAD_PRESET in .env',
      );
    }

    final url = Uri.parse(
      'https://api.cloudinary.com/v1_1/$_cloudName/$resourceType/upload',
    );

    final request = http.MultipartRequest('POST', url)
      ..fields['upload_preset'] = _uploadPreset
      ..files.add(await http.MultipartFile.fromPath('file', file.path));

    final streamed = await request.send();
    if (streamed.statusCode == 200) {
      final res = await http.Response.fromStream(streamed);
      final data = jsonDecode(res.body) as Map<String, dynamic>;
      return data['secure_url'] as String?;
    }
    return null;
  }
}
