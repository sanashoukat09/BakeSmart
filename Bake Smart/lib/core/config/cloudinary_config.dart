class CloudinaryConfig {
  static const String cloudName = 'dkhfagiw6'; // REPLACE WITH YOUR CLOUD NAME
  static const String uploadPreset = 'bakesmart_preset'; // REPLACE WITH YOUR UPLOAD PRESET
  
  static String get uploadUrl => 'https://api.cloudinary.com/v1_1/$cloudName/image/upload';
}
