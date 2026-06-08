import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:student_snapshot/core/api/api_client.dart';
import 'package:student_snapshot/core/errors/app_exception.dart';
import 'package:student_snapshot/features/snapshot/data/snapshot_models.dart';

enum SnapshotState { idle, uploading, processing, success, error }

class SnapshotProvider extends ChangeNotifier {
  final NaqlaApiClient _api;

  SnapshotProvider({NaqlaApiClient? api}) : _api = api ?? NaqlaApiClient();

  SnapshotState _state = SnapshotState.idle;
  SnapshotResponse? _result;
  String? _errorMessage;
  File? _selectedImage;
  String _statusLabel = '';

  SnapshotState get state => _state;
  SnapshotResponse? get result => _result;
  String? get errorMessage => _errorMessage;
  File? get selectedImage => _selectedImage;
  String get statusLabel => _statusLabel;

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
    _statusLabel = '';
    notifyListeners();
  }

  Future<void> submitSnapshot({
    required String tenantId,
    String? studentId,
  }) async {
    if (_selectedImage == null) {
      _errorMessage = 'لم يتم اختيار صورة.';
      _state = SnapshotState.error;
      notifyListeners();
      return;
    }

    try {
      // Step 1: get signed upload URL
      _state = SnapshotState.uploading;
      _statusLabel = 'جارٍ رفع الصورة...';
      notifyListeners();

      final urls = await _api.getImageUploadUrl(tenantId);
      await _api.uploadImage(urls.uploadUrl, _selectedImage!);

      // Step 2: submit snapshot question
      _state = SnapshotState.processing;
      _statusLabel = 'جارٍ البحث في قاعدة المعرفة...';
      notifyListeners();

      final response = await _api.submitSnapshot(
        tenantId: tenantId,
        imageRef: urls.imageRef,
        studentId: studentId,
      );
      _result = response;
      _state = SnapshotState.success;
      _statusLabel = '';
    } on AppException catch (e) {
      _errorMessage = e.message;
      _state = SnapshotState.error;
      _statusLabel = '';
    } catch (e) {
      _errorMessage = 'حدث خطأ غير متوقع. يرجى المحاولة مجدداً.';
      _state = SnapshotState.error;
      _statusLabel = '';
    }
    notifyListeners();
  }
}
