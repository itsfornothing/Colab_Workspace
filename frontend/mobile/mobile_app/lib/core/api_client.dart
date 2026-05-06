import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'constants.dart';
import 'token_storage.dart';

class ApiClient {
  static final ApiClient _instance = ApiClient._internal();
  factory ApiClient() => _instance;
  ApiClient._internal();
  ApiClient.internal();

  final _storage = TokenStorage();

  Future<Map<String, String>> _headers({bool auth = true}) async {
    final headers = {'Content-Type': 'application/json'};
    if (auth) {
      final token = await _storage.getAccessToken();
      if (token != null) headers['Authorization'] = 'Bearer $token';
    }
    return headers;
  }

  Future<http.Response> _refreshAndRetry(Future<http.Response> Function() request) async {
    final refreshToken = await _storage.getRefreshToken();
    if (refreshToken == null) throw Exception('No refresh token');

    final refreshResponse = await http.post(
      Uri.parse(AppConstants.refreshUrl),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'refresh': refreshToken}),
    );

    if (refreshResponse.statusCode == 200) {
      final data = jsonDecode(refreshResponse.body);
      await _storage.setTokens(data['access'], refreshToken);
      return await request();
    } else {
      await _storage.clearTokens();
      throw Exception('Session expired. Please log in again.');
    }
  }

  Future<http.Response> get(String url) async {
    final headers = await _headers();
    var response = await http.get(Uri.parse(url), headers: headers);
    if (response.statusCode == 401) {
      response = await _refreshAndRetry(() async {
        final h = await _headers();
        return http.get(Uri.parse(url), headers: h);
      });
    }
    return response;
  }

  Future<http.Response> post(String url, Map<String, dynamic> body, {bool auth = true}) async {
    final headers = await _headers(auth: auth);
    var response = await http.post(Uri.parse(url), headers: headers, body: jsonEncode(body));
    if (response.statusCode == 401 && auth) {
      response = await _refreshAndRetry(() async {
        final h = await _headers();
        return http.post(Uri.parse(url), headers: h, body: jsonEncode(body));
      });
    }
    return response;
  }

  Future<http.Response> patch(String url, Map<String, dynamic> body) async {
    final headers = await _headers();
    var response = await http.patch(Uri.parse(url), headers: headers, body: jsonEncode(body));
    if (response.statusCode == 401) {
      response = await _refreshAndRetry(() async {
        final h = await _headers();
        return http.patch(Uri.parse(url), headers: h, body: jsonEncode(body));
      });
    }
    return response;
  }

  Future<http.Response> delete(String url) async {
    final headers = await _headers();
    var response = await http.delete(Uri.parse(url), headers: headers);
    if (response.statusCode == 401) {
      response = await _refreshAndRetry(() async {
        final h = await _headers();
        return http.delete(Uri.parse(url), headers: h);
      });
    }
    return response;
  }

  Future<http.Response> uploadFile(
    String url,
    File file,
    String fieldName, {
    String? cloudinaryUrl,
  }) async {
    final token = await _storage.getAccessToken();
    final request = http.MultipartRequest('POST', Uri.parse(url));
    if (token != null) request.headers['Authorization'] = 'Bearer $token';
    if (cloudinaryUrl != null) request.fields['cloudinary_url'] = cloudinaryUrl;
    request.files.add(await http.MultipartFile.fromPath(fieldName, file.path));
    final streamed = await request.send();
    return http.Response.fromStream(streamed);
  }

  Future<String?> getStoredUserId() => _storage.getUserId();

  Future<http.Response> uploadFileWithField(
    String url,
    File file,
    String fieldName,
    Map<String, String> fields,
  ) async {
    final token = await _storage.getAccessToken();
    final request = http.MultipartRequest('POST', Uri.parse(url));
    if (token != null) request.headers['Authorization'] = 'Bearer $token';
    request.fields.addAll(fields);
    request.files.add(await http.MultipartFile.fromPath(fieldName, file.path));
    final streamed = await request.send();
    return http.Response.fromStream(streamed);
  }
}
