import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:student_snapshot/features/snapshot/domain/snapshot_provider.dart';
import 'package:student_snapshot/features/snapshot/presentation/access_screen.dart';

class App extends StatelessWidget {
  const App({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => SnapshotProvider()),
      ],
      child: MaterialApp(
        title: 'نقلة للطلاب',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorSchemeSeed: Colors.blue,
          useMaterial3: true,
          fontFamily: 'Roboto',
        ),
        // RTL (Arabic) layout direction
        builder: (context, child) => Directionality(
          textDirection: TextDirection.rtl,
          child: child!,
        ),
        home: const AccessScreen(),
      ),
    );
  }
}
