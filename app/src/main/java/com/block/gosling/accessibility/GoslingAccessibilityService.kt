package com.block.gosling.accessibility

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.accessibilityservice.GestureDescription
import android.content.Context
import android.content.Intent
import android.graphics.Path
import android.provider.Settings
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import android.widget.Toast
import org.json.JSONArray
import org.json.JSONObject

class GoslingAccessibilityService : AccessibilityService() {

    companion object {
        private const val TAG = "GoslingService"
        var instance: GoslingAccessibilityService? = null
            private set

        fun isServiceEnabled(context: Context): Boolean {
            val accessibilityEnabled = try {
                Settings.Secure.getInt(
                    context.contentResolver,
                    Settings.Secure.ACCESSIBILITY_ENABLED
                )
            } catch (e: Settings.SettingNotFoundException) {
                Log.e(TAG, "Error checking if accessibility is enabled", e)
                0
            }

            if (accessibilityEnabled != 1) {
                Log.d(TAG, "Accessibility is not enabled (${accessibilityEnabled})")
                return false
            }

            val serviceString = "${context.packageName}/${GoslingAccessibilityService::class.java.canonicalName}"
            val enabledServices = Settings.Secure.getString(
                context.contentResolver,
                Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
            ) ?: return false

            Log.d(TAG, "Checking service string: $serviceString")
            Log.d(TAG, "Enabled services: $enabledServices")

            return enabledServices.split(':').any { it.equals(serviceString, ignoreCase = true) }
        }
    }

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "Service created")
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        Log.i(TAG, "Service connected")
        instance = this
        
        try {
            // Configure service with full capabilities
            serviceInfo = AccessibilityServiceInfo().apply {
                eventTypes = AccessibilityEvent.TYPES_ALL_MASK
                feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC
                notificationTimeout = 100
                flags = AccessibilityServiceInfo.DEFAULT or
                        AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS or
                        AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS or
                        AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS
            }
            
            Log.i(TAG, "Service configured successfully")
            Toast.makeText(this, "Gosling Accessibility Service Connected", Toast.LENGTH_SHORT).show()
        } catch (e: Exception) {
            Log.e(TAG, "Error configuring service", e)
        }
    }

    override fun onUnbind(intent: Intent?): Boolean {
        Log.i(TAG, "Service unbound")
        return super.onUnbind(intent)
    }

    override fun onDestroy() {
        Log.i(TAG, "Service being destroyed")
        instance = null
        super.onDestroy()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        event?.let {
            Log.v(TAG, "Received event: ${event.eventType}")
        }
    }

    override fun onInterrupt() {
        Log.w(TAG, "Service interrupted")
    }

    fun performClick(x: Float, y: Float) {
        Log.d(TAG, "Performing click at ($x, $y)")
        val path = Path()
        path.moveTo(x, y)
        
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, 100))
            .build()

        dispatchGesture(gesture, object : GestureResultCallback() {
            override fun onCompleted(gestureDescription: GestureDescription?) {
                Log.d(TAG, "Click completed")
            }

            override fun onCancelled(gestureDescription: GestureDescription?) {
                Log.w(TAG, "Click cancelled")
            }
        }, null)
    }

    fun performSwipe(startX: Float, startY: Float, endX: Float, endY: Float, duration: Long = 300) {
        Log.d(TAG, "Performing swipe from ($startX, $startY) to ($endX, $endY)")
        val path = Path()
        path.moveTo(startX, startY)
        path.lineTo(endX, endY)
        
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, duration))
            .build()

        dispatchGesture(gesture, object : GestureResultCallback() {
            override fun onCompleted(gestureDescription: GestureDescription?) {
                Log.d(TAG, "Swipe completed")
            }

            override fun onCancelled(gestureDescription: GestureDescription?) {
                Log.w(TAG, "Swipe cancelled")
            }
        }, null)
    }

    fun getUiHierarchy(clean: Boolean = false): String {
        Log.d(TAG, "Getting UI hierarchy (clean=$clean)")
        val root = JSONObject()
        
        try {
            val activeWindow = rootInActiveWindow
            if (activeWindow != null) {
                try {
                    root.put("package", activeWindow.packageName)
                    root.put("class", activeWindow.className)
                    root.put("nodes", serializeNodeHierarchy(activeWindow, clean))
                } finally {
                    activeWindow.recycle()
                }
            } else {
                val msg = "No active window found"
                Log.w(TAG, msg)
                root.put("error", msg)
            }
        } catch (e: Exception) {
            val msg = "Failed to get UI hierarchy: ${e.message}"
            Log.e(TAG, msg, e)
            root.put("error", msg)
        }
        
        return root.toString(2)
    }

    private fun serializeNodeHierarchy(node: AccessibilityNodeInfo, clean: Boolean): JSONObject {
        val json = JSONObject()
        
        try {
            json.put("class", node.className)
            json.put("package", node.packageName)
            
            node.text?.toString()?.takeIf { it.isNotEmpty() }?.let {
                json.put("text", it)
            }
            
            node.contentDescription?.toString()?.takeIf { it.isNotEmpty() }?.let {
                json.put("content-desc", it)
            }

            node.viewIdResourceName?.takeIf { it.isNotEmpty() }?.let {
                json.put("resource-id", it)
            }

            val bounds = android.graphics.Rect()
            node.getBoundsInScreen(bounds)
            json.put("bounds", JSONObject().apply {
                put("left", bounds.left)
                put("top", bounds.top)
                put("right", bounds.right)
                put("bottom", bounds.bottom)
            })

            if (!clean) {
                json.put("clickable", node.isClickable)
                json.put("focusable", node.isFocusable)
                json.put("enabled", node.isEnabled)
                json.put("scrollable", node.isScrollable)
            }

            val children = JSONArray()
            for (i in 0 until node.childCount) {
                node.getChild(i)?.let { childNode ->
                    children.put(serializeNodeHierarchy(childNode, clean))
                    childNode.recycle()
                }
            }
            if (children.length() > 0) {
                json.put("children", children)
            }
        } catch (e: Exception) {
            val msg = "Failed to serialize node: ${e.message}"
            Log.e(TAG, msg, e)
            json.put("error", msg)
        }

        return json
    }
}