import 'package:flutter_dotenv/flutter_dotenv.dart';

class AppConfig {
  static String get apiBaseUrl =>
      dotenv.env['API_BASE_URL'] ??
      'https://naqla-api-dev-54067612239.europe-west1.run.app';
}
