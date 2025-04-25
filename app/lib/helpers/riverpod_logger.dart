// lib/helpers/riverpod_logger.dart
import 'package:logger/logger.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'app_logger.dart';

class RiverpodLogger extends ProviderObserver {
  final Logger _log = AppLogger.instance;

  @override
  void didUpdateProvider(ProviderBase provider, Object? previous, Object? next, ProviderContainer container) {
    _log.d(
      '[Provider] ${provider.name ?? provider.runtimeType} changed → $next',
    );
    super.didUpdateProvider(provider, previous, next, container);
  }

  @override
  void didAddProvider(ProviderBase provider, Object? value, ProviderContainer container) {
    _log.d('[Provider] ${provider.name ?? provider.runtimeType} added → $value');
    super.didAddProvider(provider, value, container);
  }

  @override
  void didDisposeProvider(ProviderBase provider, ProviderContainer container) {
    _log.d('[Provider] ${provider.name ?? provider.runtimeType} disposed');
    super.didDisposeProvider(provider, container);
  }
}
