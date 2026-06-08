import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:student_snapshot/core/api/api_client.dart';
import 'package:student_snapshot/core/errors/app_exception.dart';
import 'package:student_snapshot/features/snapshot/data/snapshot_models.dart';

enum SnapshotState { idle, loading, success, error }

class SnapshotProvider extends ChangeNotifier {
  final NaqlaApiClient _api;

  SnapshotProvider({NaqlaApiClient? api})
      : _api = api ?? NaqlaApiClient();

  SnapshotState _state = SnapshotState.idle;
  SnapshotResponse? _result;
  String? _errorMessage;
  File? _selectedImage;

  SnapshotState get state => _state;
  SnapshotResponse? get result => _result;
  String? get errorMessage => _errorMessage;
  File? get selectedImage => _selectedImage;

  void setSelectedImage(File image) {
    _selectedImage = image;
    _state = SnapshotState.idle;
    _result = null;
    _errorMessage = null;
    notifyListeners();
  }

  void reset() {
    _state = SnapshotState.idle;
    _result = null;
    _errorMessage = null;
    _selectedImage = null;
    notifyListeners();
  }

  Future<void> submitSnapshot({
    required String tenantId,
    String? ocrOverride,
    String? studentId,
  }) async {
    _state = SnapshotState.loading;
    _errorMessage = null;
    notifyListeners();

    try {
      // TODO: upload image to GCS and get signed URL, then pass image_url
      // For now, pass ocr_override for testing or leave image_url as placeholder
      final response = await _api.submitSnapshot(
        tenantId: tenantId,
        ocrOverride: ocrOverride,
        studentId: studentId,
        imageUrl: null, // TODO: replace with GCS upload URL
      );
      _result = response;
      _state = SnapshotState.success;
    } on AppException catch (e) {
      _errorMessage = e.message;
      _state = SnapshotState.error;
    } catch (e) {
      _errorMessage = 'حدث خطأ غير متوقع. يرجى المحاولة مجدداً.';
      _state = SnapshotState.error;
    }
    notifyListeners();
  }
}
