import 'dart:io';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:http/http.dart' as http;
import 'package:flutter_markdown/flutter_markdown.dart';
import '../core/theme/baker_theme.dart';

class PhotoToInstructionScreen extends StatefulWidget {
  const PhotoToInstructionScreen({super.key});

  @override
  State createState() => _PhotoToInstructionScreenState();
}

class _PhotoToInstructionScreenState extends State<PhotoToInstructionScreen> {
  File? image;
  bool loading = false;
  String ollamaUrl = "http://10.0.2.2:11434"; // Default for Android Emulator
  String ollamaModel = "qwen2.5vl:3b"; // Reverted back to the highly detailed 'qwen2.5vl:3b' model as requested by the user

  bool pulling = false;
  String pullProgressText = "";
  String ingredients = "";
  String tools = "";
  String steps = "";
  String error = "";

  final picker = ImagePicker();

  // PICK IMAGE
  Future pickImage() async {
    final picked = await picker.pickImage(
      source: ImageSource.gallery,
      maxWidth: 256, // Reduced to speed up vision processing
      maxHeight: 256, // Reduced to speed up vision processing
      imageQuality: 30, // Reduced quality to 30%
    );

    if (picked != null) {
      print("Image selected: ${picked.path}");
      setState(() {
        image = File(picked.path);
        ingredients = "";
        tools = "";
        steps = "";
        error = "";
      });
    }
  }

  // SETTINGS DIALOG
  // PULL MODEL
  Future pullModel(void Function(void Function()) setDialogState) async {
    setDialogState(() {
      pulling = true;
      pullProgressText = "Connecting...";
      error = "";
    });

    try {
      final request = http.Request('POST', Uri.parse('$ollamaUrl/api/pull'));
      request.headers['Content-Type'] = 'application/json';
      request.body = jsonEncode({
        "name": ollamaModel,
        "stream": true,
      });

      final response = await http.Client().send(request);

      if (response.statusCode == 200) {
        await for (var chunk in response.stream.transform(utf8.decoder).transform(const LineSplitter())) {
          if (chunk.isEmpty) continue;
          final data = jsonDecode(chunk);
          if (data['status'] != null) {
            String status = data['status'];
            if (data['total'] != null && data['completed'] != null) {
              double percent = (data['completed'] / data['total']) * 100;
              status += " (${percent.toStringAsFixed(1)}%)";
            }
            setDialogState(() {
               pullProgressText = status;
            });
          }
        }
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text("Successfully pulled $ollamaModel!")),
          );
        }
      } else {
        final errorBody = await response.stream.transform(utf8.decoder).join();
        setState(() {
          error = "Pull Error: ${response.statusCode}\n$errorBody";
        });
      }
    } catch (e) {
      setState(() {
        error = "Error pulling model: $e";
      });
    } finally {
      setDialogState(() {
        pulling = false;
        pullProgressText = "";
      });
    }
  }

  void _showSettingsDialog() {
    TextEditingController urlController = TextEditingController(text: ollamaUrl);
    TextEditingController modelController = TextEditingController(text: ollamaModel);
    
    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text(
            "Ollama Settings",
            style: TextStyle(fontWeight: FontWeight.bold, color: BakerTheme.textPrimary),
          ),
          backgroundColor: BakerTheme.background,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  "Server URL",
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: BakerTheme.textSecondary,
                    fontSize: 13,
                  ),
                ),
                const SizedBox(height: 6),
                TextField(
                  controller: urlController,
                  decoration: const InputDecoration(
                    hintText: "http://10.0.2.2:11434",
                    prefixIcon: Icon(Icons.dns_outlined),
                  ),
                  onChanged: (v) => ollamaUrl = v.trim(),
                ),
                const SizedBox(height: 16),
                const Text(
                  "Model Name",
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: BakerTheme.textSecondary,
                    fontSize: 13,
                  ),
                ),
                const SizedBox(height: 6),
                TextField(
                  controller: modelController,
                  decoration: const InputDecoration(
                    hintText: "qwen2.5vl:3b",
                    prefixIcon: Icon(Icons.smart_toy_outlined),
                  ),
                  onChanged: (v) => ollamaModel = v.trim(),
                ),
                const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity,
                  height: 48,
                  child: ElevatedButton.icon(
                    onPressed: pulling ? null : () async {
                      await pullModel(setDialogState);
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: BakerTheme.primary,
                      foregroundColor: Colors.white,
                      disabledBackgroundColor: BakerTheme.textMuted.withOpacity(0.3),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    icon: pulling 
                      ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : const Icon(Icons.download_outlined, size: 20),
                    label: Text(
                      pulling ? (pullProgressText.isEmpty ? "Pulling..." : pullProgressText) : "Pull Model From Server",
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                    ),
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text("Cancel"),
            ),
            ElevatedButton(
              onPressed: () {
                setState(() {
                  ollamaUrl = urlController.text.trim();
                  ollamaModel = modelController.text.trim();
                });
                Navigator.pop(context);
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: BakerTheme.secondary,
                foregroundColor: Colors.white,
                minimumSize: const Size(80, 44),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                elevation: 0,
              ),
              child: const Text("Save"),
            ),
          ],
        ),
      ),
    );
  }

  // SEND TO OLLAMA
  Future generateInstructions() async {
    print("Generate Instructions button tapped.");
    if (image == null) {
      print("Error: Image is null. Cannot generate.");
      return;
    }

    setState(() {
      loading = true;
      error = "";
    });

    try {
      final bytes = await image!.readAsBytes();
      final base64Image = base64Encode(bytes);

      print("Sending request to Ollama: $ollamaUrl/api/generate using model: $ollamaModel");
      final startTime = DateTime.now();

      final request = http.Request('POST', Uri.parse('$ollamaUrl/api/generate'));
      request.headers['Content-Type'] = 'application/json';
      request.body = jsonEncode({
        "model": ollamaModel,
        "prompt": """
                  You are a strict cake validation assistant.
                  
                  Analyze the image carefully.
                  
                  1. If the image is NOT a cake (e.g. car, tree, animal, person, food other than cake, or landscape),
                  you must start your response with:
                  
                  CATEGORY: OTHER
                  
                  Then briefly explain why it is not a cake.
                  
                  2. If the image IS a cake, start your response with:
                  
                  CATEGORY: CAKE
                  
                  Then generate a detailed and beginner-friendly recipe based on the cake visible in the image.
                  
                  Important rules for cake recipes:
                  - Provide a COMPLETE ingredient list with estimated quantities.
                  - Do NOT provide only a few ingredients.
                  - Include cake base ingredients, frosting/cream, filling, syrup, toppings, and decoration ingredients if visible or likely.
                  - Make reasonable estimates for hidden ingredients.
                  - Steps must be very clear, detailed, and easy to follow.
                  - Include oven temperature, baking time, cooling time, frosting, assembling, and decoration instructions.
                  - Mention preparation tips where helpful.
                  
                  For cakes, use these headers exactly:
                  
                  ### INGREDIENTS
                  Include:
                  - Cake Base
                  - Frosting / Cream
                  - Filling (if applicable)
                  - Toppings / Decoration
                  
                  ### TOOLS
                  List all required tools and baking equipment.
                  
                  ### STEPS
                  Provide detailed numbered steps from preparation to serving.
                  """,
        "images": [base64Image],
        "stream": true,
        "options": {
          "num_ctx": 2048
        }
      });

      print("Sending streaming request to Ollama: $ollamaUrl/api/generate using model: $ollamaModel");
      final response = await http.Client().send(request);

      print("Received initial response stream from Ollama. Status: ${response.statusCode}");

      if (response.statusCode == 200) {
        String fullText = "";
        
        await for (var chunk in response.stream.transform(utf8.decoder).transform(const LineSplitter())) {
          if (chunk.isEmpty) continue;
          
          final data = jsonDecode(chunk);
          if (data['response'] != null) {
            fullText += data['response'] as String;
            
            // Live update the UI
            setState(() {
              if (fullText.toUpperCase().contains("CATEGORY: OTHER") && !fullText.toUpperCase().contains("CATEGORY: CAKE")) {
                 error = "This is not the image of a cake!";
                 ingredients = "";
                 tools = "";
                 steps = "";
              } else {
                 _parseResponse(fullText);
              }
            });
          }
        }
        final endTime = DateTime.now();
        print("Completed stream in ${endTime.difference(startTime).inSeconds}s");
      } else {
        final errorBody = await response.stream.transform(utf8.decoder).join();
        String msg = "Server Error: ${response.statusCode}\n$errorBody";
        if (response.statusCode == 404) {
          msg = "Model '$ollamaModel' not found on server!\n\nGo to Settings and click 'Pull Model' to download it.";
        }
        setState(() {
          error = msg;
        });
      }
    } catch (e) {
      setState(() {
        error = "Error connecting to Ollama: $e\n\nMake sure your Ollama server is running and accessible on the network.";
      });
    } finally {
      setState(() {
        loading = false;
      });
    }
  }

  void _parseResponse(String text) {
    // Simple parsing logic based on markers
    String ing = "";
    String tol = "";
    String stp = "";

    try {
      final parts = text.split(RegExp(r'###\s*(INGREDIENTS|TOOLS|STEPS)'));
      // The first part is usually empty or intro text
      // We need to find where each marker was to assign correctly

      RegExp markerExp = RegExp(r'###\s*(INGREDIENTS|TOOLS|STEPS)');
      Iterable<Match> matches = markerExp.allMatches(text);

      int i = 1;
      for (var match in matches) {
        String marker = match.group(1)!;
        String content = i < parts.length ? parts[i].trim() : "";

        if (marker == "INGREDIENTS") ing = content;
        if (marker == "TOOLS") tol = content;
        if (marker == "STEPS") stp = content;
        i++;
      }

      // Fallback if parsing fails or model ignores format
      if (ing.isEmpty && tol.isEmpty && stp.isEmpty) {
        // Clean up the CATEGORY marker if it's there
        String cleanText = text.replaceFirst(RegExp(r'(?i)CATEGORY:\s*CAKE'), '').trim();
        if (cleanText.isEmpty) {
          ing = "Generating response...";
        } else {
          ing = cleanText;
        }
        tol = "The AI provided a general response. Please check the Ingredients tab.";
        stp = "The AI provided a general response. Please check the Ingredients tab.";
      }
    } catch (e) {
      ing = "Error parsing response: $e\n\nOriginal Text:\n$text";
    }

    setState(() {
      ingredients = ing;
      tools = tol;
      steps = stp;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: BakerTheme.background,
      appBar: AppBar(
        title: const Text(
          "BakeSmart AI",
          style: TextStyle(fontWeight: FontWeight.bold, color: BakerTheme.textPrimary),
        ),
        centerTitle: true,
        backgroundColor: BakerTheme.background,
        elevation: 0,
        iconTheme: const IconThemeData(color: BakerTheme.textPrimary),
        actions: [
          IconButton(
            onPressed: _showSettingsDialog,
            icon: const Icon(Icons.settings, color: BakerTheme.textPrimary),
          ),
        ],
      ),
      body: Column(
        children: [
          // HEADER DESIGN
          Container(
            margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: BakerTheme.primary, // Premium Espresso Brown
              borderRadius: BorderRadius.circular(24),
              boxShadow: [
                BoxShadow(
                  color: BakerTheme.primary.withOpacity(0.2),
                  blurRadius: 15,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            child: Column(
              children: [
                GestureDetector(
                  onTap: pickImage,
                  child: Container(
                    height: 180,
                    width: double.infinity,
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.08),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: Colors.white.withOpacity(0.2), width: 1.5),
                      image: image != null
                          ? DecorationImage(image: FileImage(image!), fit: BoxFit.cover)
                          : null,
                    ),
                    child: image == null
                        ? const Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.add_a_photo_outlined, color: Colors.white70, size: 50),
                              SizedBox(height: 12),
                              Text(
                                "Upload Cake Image",
                                style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 15),
                              ),
                            ],
                          )
                        : null,
                  ),
                ),
                const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: ElevatedButton(
                    onPressed: loading ? null : generateInstructions,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: BakerTheme.secondary, // Amber Secondary
                      foregroundColor: Colors.white,
                      disabledBackgroundColor: BakerTheme.textMuted.withOpacity(0.3),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                      elevation: 0,
                    ),
                    child: loading
                        ? const Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              SizedBox(
                                height: 20,
                                width: 20,
                                child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white),
                              ),
                              SizedBox(width: 15),
                              Text(
                                "AI is Baking...",
                                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white),
                              ),
                            ],
                          )
                        : const Text(
                            "Generate Instructions",
                            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white),
                          ),
                  ),
                ),
              ],
            ),
          ),

          if (error.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: BakerTheme.error.withOpacity(0.08),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: BakerTheme.error.withOpacity(0.2), width: 1.5),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.error_outline, color: BakerTheme.error),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        error,
                        style: const TextStyle(color: BakerTheme.error, fontWeight: FontWeight.w600, fontSize: 13.5),
                      ),
                    ),
                  ],
                ),
              ),
            ),

          const SizedBox(height: 10),

          // RESULT TABS
          Expanded(
            child: DefaultTabController(
              length: 3,
              child: Column(
                children: [
                  const TabBar(
                    labelColor: BakerTheme.primary,
                    unselectedLabelColor: BakerTheme.textMuted,
                    indicatorColor: BakerTheme.primary,
                    indicatorWeight: 3,
                    indicatorSize: TabBarIndicatorSize.tab,
                    dividerColor: BakerTheme.divider,
                    labelStyle: TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                    unselectedLabelStyle: TextStyle(fontWeight: FontWeight.normal, fontSize: 14),
                    tabs: [
                      Tab(icon: Icon(Icons.shopping_basket_outlined), text: "Ingredients"),
                      Tab(icon: Icon(Icons.handyman_outlined), text: "Tools"),
                      Tab(icon: Icon(Icons.format_list_numbered_outlined), text: "Steps"),
                    ],
                  ),
                  Expanded(
                    child: Container(
                      color: BakerTheme.background,
                      child: TabBarView(
                        children: [
                          _buildContentList(ingredients),
                          _buildContentList(tools),
                          _buildContentList(steps),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildContentList(String content) {
    if (content.isEmpty) {
      return const Center(
        child: Text(
          "No data available. Upload an image to start.",
          style: TextStyle(color: BakerTheme.textMuted, fontWeight: FontWeight.w500),
        ),
      );
    }
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: MarkdownBody(
        data: content,
        styleSheet: MarkdownStyleSheet(
          p: const TextStyle(fontSize: 15, height: 1.6, color: BakerTheme.textPrimary),
          h1: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: BakerTheme.textPrimary),
          h2: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: BakerTheme.textPrimary),
          h3: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: BakerTheme.textPrimary),
          listBullet: const TextStyle(color: BakerTheme.secondary, fontSize: 15),
        ),
      ),
    );
  }
}