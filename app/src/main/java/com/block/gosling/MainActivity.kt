package com.block.gosling

import android.content.Intent
import android.os.Bundle
import android.provider.Settings
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
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }

        binding.submitButton.setOnClickListener {
            val command = binding.commandInput.text?.toString()
            if (command.isNullOrBlank()) {
                Toast.makeText(this, "Please enter a command", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            // TODO: Send command to accessibility service
            Toast.makeText(this, "Command received: $command", Toast.LENGTH_SHORT).show()
        }
    }

    private fun updateServiceStatus() {
        val isServiceEnabled = GoslingAccessibilityService.isServiceEnabled(this)
        binding.serviceStatus.text = getString(R.string.service_status, 
            if (isServiceEnabled) "Enabled" else "Disabled")
        binding.enableAccessibilityButton.isEnabled = !isServiceEnabled
        binding.submitButton.isEnabled = isServiceEnabled
        binding.commandInput.isEnabled = isServiceEnabled
    }
}