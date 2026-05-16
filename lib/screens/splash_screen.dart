import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/splash_provider.dart';

// ─── Sparkle configs ─────────────────────────────────────────────────────────

const List<_SparkleConfig> _splashSparkles = [
  _SparkleConfig(left: 42, top: 36, size: 3.5, delay: 0.00),
  _SparkleConfig(left: 82, top: 20, size: 4.5, delay: 0.35),
  _SparkleConfig(left: 120, top: 40, size: 3.5, delay: 0.70),
];

// ─────────────────────────────────────────────────────────────────────────────

class SplashScreen extends ConsumerStatefulWidget {
  const SplashScreen({super.key});

  @override
  ConsumerState<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<SplashScreen>
    with TickerProviderStateMixin {

  late final AnimationController _introController;
  late final AnimationController _floatController;

  late final Animation<double> _logoOpacity;
  late final Animation<double> _logoScale;
  late final Animation<Offset> _logoSlide;
  late final Animation<double> _textOpacity;
  late final Animation<Offset> _textSlide;

  @override
  void initState() {
    super.initState();

    // ── Intro: one-shot entrance ─────────────────────────────────────────────
    _introController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    );

    // ── Float: continuous loop, starts AFTER intro completes ─────────────────
    // 3200ms = one full up-and-down cycle. Feels slow & premium.
    _floatController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 3200),
    );

    // ── Logo entrance animations ─────────────────────────────────────────────
    _logoOpacity = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _introController,
        curve: const Interval(0.0, 0.5, curve: Curves.easeOut),
      ),
    );

    _logoScale = Tween<double>(begin: 0.82, end: 1.0).animate(
      CurvedAnimation(
        parent: _introController,
        // easeOutBack gives a subtle satisfying overshoot
        curve: const Interval(0.0, 0.70, curve: Curves.easeOutBack),
      ),
    );

    _logoSlide = Tween<Offset>(
      begin: const Offset(0, 0.10),
      end: Offset.zero,
    ).animate(
      CurvedAnimation(
        parent: _introController,
        curve: const Interval(0.0, 0.70, curve: Curves.easeOutCubic),
      ),
    );

    // ── Text entrance animations ──────────────────────────────────────────────
    _textOpacity = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _introController,
        curve: const Interval(0.45, 1.0, curve: Curves.easeOut),
      ),
    );

    _textSlide = Tween<Offset>(
      begin: const Offset(0, 0.14),
      end: Offset.zero,
    ).animate(
      CurvedAnimation(
        parent: _introController,
        curve: const Interval(0.45, 1.0, curve: Curves.easeOutCubic),
      ),
    );

    // ── Sequence: intro finishes → float begins ───────────────────────────────
    // whenCompleteOrCancel ensures float starts even if intro is interrupted.
    // addPostFrameCallback pins the start to the next vsync — zero stutter.
    _introController.forward().whenCompleteOrCancel(() {
      if (!mounted) return;
      SchedulerBinding.instance.addPostFrameCallback((_) {
        if (mounted) _floatController.repeat();
      });
    });

    // ── Splash minimum display time ───────────────────────────────────────────
    Future.delayed(const Duration(milliseconds: 2800), () {
      if (mounted) {
        ref.read(splashMinTimeElapsedProvider.notifier).state = true;
      }
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    precacheImage(
      const AssetImage('assets/images/bakesmart_logo.png'),
      context,
    );
  }

  @override
  void dispose() {
    _introController.dispose();
    _floatController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFDFCF9),
      body: SafeArea(
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _SplashLogo(
                logoOpacity: _logoOpacity,
                logoScale: _logoScale,
                logoSlide: _logoSlide,
                floatController: _floatController,
              ),
              const SizedBox(height: 16),
              _SplashText(
                textOpacity: _textOpacity,
                textSlide: _textSlide,
              ),
              const SizedBox(height: 56),
            ],
          ),
        ),
      ),
    );
  }
}

// ─── Logo widget ──────────────────────────────────────────────────────────────

class _SplashLogo extends StatelessWidget {
  const _SplashLogo({
    required this.logoOpacity,
    required this.logoScale,
    required this.logoSlide,
    required this.floatController,
  });

  final Animation<double> logoOpacity;
  final Animation<double> logoScale;
  final Animation<Offset> logoSlide;
  final AnimationController floatController;

  /// TRUE up-and-down float using a full sine wave.
  ///
  /// sin(t × 2π) over t ∈ [0, 1] produces:
  ///   t=0.00 → 0   (rest)
  ///   t=0.25 → +1  → we negate → logo UP   ← peak lift
  ///   t=0.50 → 0   (rest)
  ///   t=0.75 → −1  → we negate → logo DOWN ← gentle dip
  ///   t=1.00 → 0   (rest, seamlessly loops)
  ///
  /// travelPx = 8: subtle but clearly visible on any screen size.
  static double _floatY(double t, double travelPx) {
    return -math.sin(t * 2 * math.pi) * travelPx;
  }

  @override
  Widget build(BuildContext context) {
    return SlideTransition(
      position: logoSlide,
      child: FadeTransition(
        opacity: logoOpacity,
        child: ScaleTransition(
          scale: logoScale,
          // Isolate intro transition repaints from the continuous float layer
          child: RepaintBoundary(
            child: AnimatedBuilder(
              animation: floatController,
              builder: (context, child) {
                final logoY = _floatY(floatController.value, 8.0);

                // liftFraction: 0 at rest, 1 at peak (logo fully up)
                // Only shrink shadow when logo rises, not when it dips
                final liftFraction = (-logoY / 8.0).clamp(0.0, 1.0);
                final shadowScaleX =
                    (1.0 - liftFraction * 0.22).clamp(0.78, 1.0);
                final shadowOpacity =
                    (0.20 - liftFraction * 0.12).clamp(0.07, 0.20);

                return SizedBox(
                  width: 170,
                  // Extra height so shadow never clips at the bottom
                  height: 200,
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      // Sparkles — each has its own phase offset
                      for (final cfg in _splashSparkles)
                        _SparkleWidget(
                          cfg: cfg,
                          floatController: floatController,
                        ),

                      // Logo — Transform.translate is a free compositor op
                      // when the child has its own RepaintBoundary layer.
                      Positioned(
                        top: 8,
                        child: Transform.translate(
                          offset: Offset(0, logoY),
                          child: child, // ← cached GPU texture, never repaints
                        ),
                      ),

                      // Shadow reacts opposite to logo position
                      Positioned(
                        bottom: 8,
                        child: Transform.scale(
                          scaleX: shadowScaleX,
                          child: Opacity(
                            opacity: shadowOpacity,
                            child: const _ShadowBlob(),
                          ),
                        ),
                      ),
                    ],
                  ),
                );
              },
              // Built once → RepaintBoundary → cached as GPU texture.
              // The Transform.translate above just repositions it — zero cost.
              child: RepaintBoundary(
                child: Image.asset(
                  'assets/images/bakesmart_logo.png',
                  width: 148,
                  height: 148,
                  fit: BoxFit.contain,
                  filterQuality: FilterQuality.high,
                  gaplessPlayback: true,
                  isAntiAlias: true,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// ─── Text widget ──────────────────────────────────────────────────────────────

class _SplashText extends StatelessWidget {
  const _SplashText({
    required this.textOpacity,
    required this.textSlide,
  });

  final Animation<double> textOpacity;
  final Animation<Offset> textSlide;

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: textOpacity,
      child: SlideTransition(
        position: textSlide,
        child: const RepaintBoundary(
          child: Column(
            children: [
              Text(
                'BakeSmart',
                style: TextStyle(
                  color: Color(0xFF8B5A2B),
                  fontSize: 34,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 3.2,
                  fontFamily: 'serif',
                ),
              ),
              SizedBox(height: 7),
              Text(
                'The Secret Ingredient is AI',
                style: TextStyle(
                  color: Color(0xFF5D4037),
                  fontSize: 14,
                  fontWeight: FontWeight.w400,
                  letterSpacing: 1.1,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ─── Sparkle widget ───────────────────────────────────────────────────────────

class _SparkleWidget extends StatelessWidget {
  const _SparkleWidget({
    required this.cfg,
    required this.floatController,
  });

  final _SparkleConfig cfg;
  final AnimationController floatController;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: floatController,
      builder: (context, child) {
        final progress = (floatController.value + cfg.delay) % 1.0;
        final fade = math.sin(progress * math.pi).clamp(0.0, 1.0);
        final y = -10.0 * fade;

        return Positioned(
          left: cfg.left,
          top: cfg.top + y,
          child: Opacity(
            opacity: (fade * 0.65).clamp(0.0, 1.0),
            child: child,
          ),
        );
      },
      child: RepaintBoundary(
        child: SizedBox(
          width: cfg.size,
          height: cfg.size,
          child: const DecoratedBox(
            decoration: BoxDecoration(
              color: Color(0xFFB8794C),
              shape: BoxShape.circle,
            ),
          ),
        ),
      ),
    );
  }
}

// ─── Shadow blob ──────────────────────────────────────────────────────────────

class _ShadowBlob extends StatelessWidget {
  const _ShadowBlob();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 96,
      height: 8,
      decoration: BoxDecoration(
        color: const Color(0xFFB8794C),
        borderRadius: BorderRadius.circular(50),
      ),
    );
  }
}

// ─── Sparkle config ───────────────────────────────────────────────────────────

class _SparkleConfig {
  const _SparkleConfig({
    required this.left,
    required this.top,
    required this.size,
    required this.delay,
  });

  final double left;
  final double top;
  final double size;
  final double delay;
}