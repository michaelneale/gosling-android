# Gosling Android

An AI-powered Android accessibility service that can autonomously operate your phone using natural language commands.

## Overview

Gosling Android is a native Kotlin implementation of the Gosling concept, which allows an AI assistant to operate your Android phone through natural language instructions. The app runs directly on the device and uses Android's Accessibility APIs to interact with other applications.

## Technical Architecture

### Core Components

1. **Accessibility Service**
   - Implement an Android AccessibilityService
   - Permissions required:
     - BIND_ACCESSIBILITY_SERVICE
     - SYSTEM_ALERT_WINDOW (for potential UI overlays)
     - INTERNET (for API communication)
   - Capabilities to request:
     - `AccessibilityServiceInfo.CAPABILITY_CAN_PERFORM_GESTURES`
     - Window state monitoring
     - Content capture
     - Interactive UI control

2. **AI Integration**
   - OpenAI API client for Android
   - System prompt adaptation for Android context
   - Tool definitions for Android-specific actions
   - Message history management
   - Response parsing and execution

3. **Device Interaction Layer**
   - Screen content capture and analysis
   - UI hierarchy inspection
   - Gesture execution
   - Text input handling
   - App launching and navigation

### Key Features to Implement

1. **UI Analysis**
   - Convert AccessibilityNodeInfo to structured format
   - Screen content OCR when needed
   - Element location mapping
   - Interactive element detection

2. **Action Execution**
   - Click/tap simulation
   - Text input
   - Gesture performance
   - Scrolling
   - App switching
   - Text selection and copying

3. **System Integration**
   - Background service management
   - Notification handling
   - Permission management
   - Battery optimization exclusion

4. **Safety & Privacy**
   - Local processing where possible
   - Sensitive content filtering
   - User consent management
   - Action confirmation system
   - Rate limiting

### Implementation Steps

1. **Initial Setup**
   ```kotlin
   // Base accessibility service
   class GoslingAccessibilityService : AccessibilityService() {
       override fun onAccessibilityEvent(event: AccessibilityEvent) {
           // Handle accessibility events
       }
       
       override fun onInterrupt() {
           // Handle interruption
       }
       
       override fun onServiceConnected() {
           // Configure service capabilities
       }
   }
   ```

2. **UI Interaction Tools**
   ```kotlin
   class DeviceController(private val service: AccessibilityService) {
       fun click(x: Int, y: Int) {
           // Implement click via GestureDescription
       }
       
       fun enterText(text: String) {
           // Handle text input
       }
       
       fun startApp(packageName: String) {
           // Launch applications
       }
       
       fun captureScreen(): Bitmap {
           // Implement screen capture
       }
   }
   ```

3. **AI Integration**
   ```kotlin
   class AIController(private val deviceController: DeviceController) {
       private val openAI = OpenAI(apiKey = "...")
       
       suspend fun processCommand(userInput: String) {
           // Handle AI interaction and command execution
       }
       
       private fun buildSystemPrompt(): String {
           // Create context-aware system prompt
       }
   }
   ```

## Key Differences from Python Version

1. **Native Integration**
   - Direct access to Android APIs instead of ADB
   - More reliable and faster execution
   - Better error handling and recovery
   - Real-time UI updates

2. **Enhanced Capabilities**
   - Direct accessibility node traversal
   - Native gesture support
   - Better app state management
   - System-level integration

3. **Performance Optimization**
   - Reduced latency without ADB
   - More efficient screen capture
   - Better memory management
   - Battery optimization

## Future Enhancements

1. **Local Processing**
   - Implement on-device LLMs
   - Reduce API dependency
   - Improve privacy

2. **Advanced UI Understanding**
   - ML-based element recognition
   - Context-aware interaction
   - Dynamic UI adaptation

3. **Enhanced Security**
   - Fine-grained permissions
   - Action verification
   - Secure data handling

## Getting Started

1. Clone the repository
2. Add your OpenAI API key to local.properties
3. Build and install the app
4. Enable accessibility service
5. Grant necessary permissions
6. Start using natural language commands

## Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests for any enhancements.

## License

[Add appropriate license information]