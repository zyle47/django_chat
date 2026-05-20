package com.djangochat.app

import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.View
import android.webkit.*
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import info.guardianproject.netcipher.webkit.WebkitProxy

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var statusText: TextView
    private var fileUploadCallback: ValueCallback<Array<Uri>>? = null
    private var receiverRegistered = false

    private val torStatusReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            val status = intent.getStringExtra("org.torproject.android.intent.extra.STATUS") ?: return
            when (status) {
                "ON" -> runOnUiThread { connectAndLoad() }
                "STARTING" -> runOnUiThread {
                    statusText.text = "Connecting to Tor…"
                    statusText.visibility = View.VISIBLE
                }
                "OFF" -> runOnUiThread {
                    Toast.makeText(this@MainActivity, "Orbot stopped", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private val filePickerLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            val uris = if (result.resultCode == Activity.RESULT_OK) {
                WebChromeClient.FileChooserParams.parseResult(result.resultCode, result.data)
            } else null
            fileUploadCallback?.onReceiveValue(uris)
            fileUploadCallback = null
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webView)
        statusText = findViewById(R.id.statusText)

        ViewCompat.setOnApplyWindowInsetsListener(webView.parent as View) { v, insets ->
            val bars = insets.getInsets(
                WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout()
            )
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            WindowInsetsCompat.CONSUMED
        }

        setupWebView()
        if (BuildConfig.USE_TOR) {
            initOrbot()
        } else {
            statusText.visibility = View.GONE
            webView.loadUrl(BuildConfig.BASE_URL)
        }
    }

    private fun setupWebView() {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            useWideViewPort = true
            loadWithOverviewMode = true
            setSupportZoom(false)
            builtInZoomControls = false
        }

        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView, url: String) {
                statusText.visibility = View.GONE
            }

            override fun onReceivedError(
                view: WebView,
                request: WebResourceRequest,
                error: WebResourceError
            ) {
                if (request.isForMainFrame) {
                    view.loadData(errorPage(), "text/html", "UTF-8")
                }
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(
                webView: WebView,
                filePathCallback: ValueCallback<Array<Uri>>,
                fileChooserParams: FileChooserParams
            ): Boolean {
                fileUploadCallback?.onReceiveValue(null)
                fileUploadCallback = filePathCallback
                filePickerLauncher.launch(fileChooserParams.createIntent())
                return true
            }
        }
    }

    private fun isOrbotInstalled(): Boolean {
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                packageManager.getPackageInfo("org.torproject.android", PackageManager.PackageInfoFlags.of(0))
            } else {
                @Suppress("DEPRECATION")
                packageManager.getPackageInfo("org.torproject.android", 0)
            }
            true
        } catch (e: PackageManager.NameNotFoundException) {
            false
        }
    }

    private fun initOrbot() {
        if (!isOrbotInstalled()) {
            AlertDialog.Builder(this)
                .setTitle("Orbot required")
                .setMessage("This app connects over Tor and requires Orbot. Install it to continue.")
                .setPositiveButton("Install") { _, _ ->
                    try {
                        startActivity(
                            Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=org.torproject.android"))
                        )
                    } catch (_: Exception) {
                        startActivity(
                            Intent(Intent.ACTION_VIEW, Uri.parse("https://play.google.com/store/apps/details?id=org.torproject.android"))
                        )
                    }
                    finish()
                }
                .setNegativeButton("Exit") { _, _ -> finish() }
                .setCancelable(false)
                .show()
            return
        }

        val filter = IntentFilter("org.torproject.android.intent.action.STATUS")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(torStatusReceiver, filter, RECEIVER_EXPORTED)
        } else {
            @Suppress("UnspecifiedRegisterReceiverFlag")
            registerReceiver(torStatusReceiver, filter)
        }
        receiverRegistered = true

        statusText.text = "Connecting to Tor…"
        statusText.visibility = View.VISIBLE

        val startIntent = Intent("org.torproject.android.intent.action.START")
        startIntent.setPackage("org.torproject.android")
        startIntent.putExtra("org.torproject.android.intent.extra.PACKAGE_NAME", packageName)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(startIntent)
            } else {
                startService(startIntent)
            }
        } catch (_: Exception) {
            try {
                startActivity(startIntent)
            } catch (e: Exception) {
                Toast.makeText(this, "Could not start Orbot: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }

        // If Orbot is already running it won't re-broadcast ON — try the proxy immediately.
        webView.postDelayed({
            if (statusText.visibility == View.VISIBLE) {
                connectAndLoad()
            }
        }, 1500)
    }

    private fun connectAndLoad() {
        try {
            WebkitProxy.setProxy(applicationContext.packageName, applicationContext, webView, "127.0.0.1", 8118)
            webView.loadUrl(BuildConfig.BASE_URL)
        } catch (e: Exception) {
            Toast.makeText(this, "Proxy error: ${e.message}", Toast.LENGTH_LONG).show()
        }
    }

    private fun errorPage() = """
        <html>
        <body style="background:#111;color:#eee;font-family:monospace;padding:40px;text-align:center;">
        <h2>Connection failed</h2>
        <p>Make sure Orbot is running and connected to Tor.</p>
        <button onclick="window.location.reload()"
            style="padding:12px 24px;margin-top:16px;background:#333;color:#eee;border:1px solid #555;border-radius:4px;cursor:pointer;">
            Retry
        </button>
        </body>
        </html>
    """.trimIndent()

    @Suppress("DEPRECATION")
    override fun onBackPressed() {
        if (webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }

    override fun onDestroy() {
        if (receiverRegistered) {
            unregisterReceiver(torStatusReceiver)
            receiverRegistered = false
        }
        super.onDestroy()
    }
}
