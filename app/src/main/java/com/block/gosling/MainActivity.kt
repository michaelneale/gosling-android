package com.block.gosling

import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.util.Log
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.block.gosling.databinding.ActivityMainBinding
import com.block.gosling.accessibility.GoslingAccessibilityService

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupUI()
        updateServiceStatus()
    }

    override fun onResume() {
        super.onResume()
        updateServiceStatus()
    }

    private fun setupUI() {
        binding.enableAccessibilityButton.setOnClickListener {
            Log.d("Gosling", "Button clicked - trying to open settings")
            Toast.makeText(this, "Opening settings...", Toast.LENGTH_SHORT).show()
            
            try {
                val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
                startActivity(intent)
            } catch (e: Exception) {
                Log.e("Gosling", "Failed to open settings", e)
                Toast.makeText(this, "Error: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }

        binding.submitButton.setOnClickListener { view ->
            view.isEnabled = false
            val command = binding.commandInput.text?.toString()
            if (command.isNullOrBlank()) {
                Toast.makeText(this, "Please enter a command", Toast.LENGTH_SHORT).show()
                view.isEnabled = true
                return@setOnClickListener
            }

            val service = GoslingAccessibilityService.instance
            if (service != null) {
                // TODO: Implement command processing with LLM
                // For now, just demonstrate basic gesture capability
                when {
                    command.startsWith("click") -> {
                        val parts = command.split(" ")
                        if (parts.size == 3) {
                            try {
                                val x = parts[1].toFloat()
                                val y = parts[2].toFloat()
                                service.performClick(x, y)
                                Toast.makeText(this, "Clicked at ($x, $y)", Toast.LENGTH_SHORT).show()
                            } catch (e: Exception) {
                                Toast.makeText(this, "Invalid coordinates", Toast.LENGTH_SHORT).show()
                            }
                        }
                    }
                    command == "dump" -> {
                        val hierarchy = service.getUiHierarchy(clean = false)
                        binding.commandInput.setText(hierarchy)
                    }
                    else -> {
                        Toast.makeText(this, "Unknown command: $command", Toast.LENGTH_SHORT).show()
                    }
                }
            } else {
                Toast.makeText(this, "Service not running", Toast.LENGTH_SHORT).show()
            }
            view.isEnabled = true
        }
    }

    private fun updateServiceStatus() {
        val isServiceEnabled = GoslingAccessibilityService.isServiceEnabled(this)
        Log.d("Gosling", "Service enabled: $isServiceEnabled")
        
        binding.serviceStatus.text = getString(R.string.service_status, 
            if (isServiceEnabled) "Enabled" else "Disabled")
        binding.enableAccessibilityButton.isEnabled = !isServiceEnabled
        binding.submitButton.isEnabled = isServiceEnabled
    }
}