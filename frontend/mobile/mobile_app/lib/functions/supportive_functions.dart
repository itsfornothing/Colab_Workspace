import 'dart:io';
import 'dart:convert';
import 'package:path/path.dart' as path;
import 'package:http/http.dart' as http;

/// Upload image to Cloudinary and return the secure URL
Future<String?> uploadToCloudinary(File file) async {
  const cloudName = "dmao35yzf";
  const uploadPreset = "portfolio_unsigned_preset";

  final url = Uri.parse("https://api.cloudinary.com/v1_1/$cloudName/upload");

  try {
    var request = http.MultipartRequest("POST", url)
      ..fields['upload_preset'] = uploadPreset
      ..files.add(await http.MultipartFile.fromPath('file', file.path));

    var response = await request.send();

    if (response.statusCode == 200) {
      final res = await http.Response.fromStream(response);
      final responseData = jsonDecode(res.body);
      return responseData['secure_url'] as String?;
    } else {
      return null;
    }
  } catch (e) {
    return null;
  }
}
