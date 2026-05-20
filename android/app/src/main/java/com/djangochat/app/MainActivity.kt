package com.djangochat.app

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.webkit.*
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import info.guardianproject.netcipher.proxy.OrbotHelper
import info.guardianproject.netcipher.webkit.WebkitProxy

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var statusText: TextView
    private var fileUploadCallback: ValueCallback<Array<Uri>>? = null

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

        setupWebView()
        initOrbot()
    }

    private fun setupWebView() {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            allowFileAccess = false
            allowContentAccess = false
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

    private fun initOrbot() {
        if (!OrbotHelper.isOrbotInstalled(this)) {
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

        OrbotHelper.get(this).init(this)
        OrbotHelper.get(this).addStatusCallback(object : OrbotHelper.StatusCallback {
            override fun onEnabled(intent: Intent?) {
                runOnUiThread { connectAndLoad() }
            }

            override fun onStarting() {
                runOnUiThread {
                    statusText.text = "Connecting to Tor…"
                    statusText.visibility = View.VISIBLE
                }
            }

            override fun onStopped() {
                runOnUiThread {
                    Toast.makeText(this@MainActivity, "Orbot stopped", Toast.LENGTH_SHORT).show()
                }
            }

            override fun onStatusTimeout() {
                runOnUiThread {
                    Toast.makeText(this@MainActivity, "Tor connection timed out, retrying…", Toast.LENGTH_SHORT).show()
                    OrbotHelper.requestStartTor(this@MainActivity)
                }
            }

            override fun onNotYetInstalled() {
                runOnUiThread { finish() }
            }
        })

        if (OrbotHelper.isOrbotRunning(this)) connectAndLoad()
        else OrbotHelper.requestStartTor(this)
    }

    private fun connectAndLoad() {
        try {
            WebkitProxy.setProxy(applicationContext, "127.0.0.1", 8118)
            webView.loadUrl(BuildConfig.ONION_URL)
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
        OrbotHelper.get(this).removeStatusCallback(null)
        super.onDestroy()
    }
}
