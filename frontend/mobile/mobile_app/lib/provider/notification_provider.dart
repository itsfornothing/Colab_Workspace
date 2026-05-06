import 'package:flutter_riverpod/legacy.dart';

class BgNotifier extends StateNotifier<bool> {
  BgNotifier() : super(false); // default light mode

  void toggleTheme() {
    state = !state;
  }
}

final notificationsEnabledProvider = StateProvider<bool>((ref) => false);
final bgProvider = StateNotifierProvider<BgNotifier, bool>((ref) {
  return BgNotifier();
});