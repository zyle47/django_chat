# Setup Guide

This project supports two deployment modes for the Django chat:

- **Tor hidden service** (`.onion`) — anonymity, no DNS/domain needed, requires Orbot on Android.
- **Clearnet** (normal domain over HTTPS) — Play Store friendly, easier discovery, no Tor dependency.

The Android client can be built to target either one (or be switched at build time). They can also run side-by-side on the same server.

---

## 1. Server: Tor hidden service

This is what `docker-compose.yml` does out of the box.

### One-time setup

Create `.env` in the project root:

```ini
SECRET_KEY=replace-with-50-random-chars
DEBUG=False
ADMIN_URL=some-random-admin-path
# ONION_HOST is filled in after first boot (see below)
ONION_HOST=
```

### Bring it up

```bash
docker compose up -d --build
```

### Get the `.onion` address

Tor generates the hidden service key on first boot. After the `tor` container has started:

```bash
docker compose exec tor cat /var/lib/tor/django_chat/hostname
```

Copy the printed `xxxxx.onion` value into `.env` as `ONION_HOST=`, then restart Django so `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` pick it up:

```bash
docker compose restart django-chat
```

### Verify

Open Tor Browser on any machine and visit `http://<your-onion>.onion`. You should get the chat login.

### Files involved

- [tor/torrc](tor/torrc) — Tor config. `SocksPort 0` means this node is hidden-service-only, no SOCKS proxying.
- [tor/Dockerfile](tor/Dockerfile) — Alpine + tor.
- `tor-data/` — generated on first run, contains the hidden service private key. **Back this up** — losing it means losing the onion address.

---

## 2. Server: Clearnet (domain + HTTPS)

The current `docker-compose.yml` does **not** include a clearnet entrypoint — you need to add one. Easiest is Caddy (automatic Let's Encrypt).

### a. Point DNS

Create an A record `chat.yourdomain.com` → your server's public IP. Open ports 80 and 443 on the firewall.

### b. Add Caddy to docker-compose

Append to `docker-compose.yml`:

```yaml
  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy-data:/data
      - caddy-config:/config
    depends_on:
      - django-chat
    networks:
      - internal

volumes:
  caddy-data:
  caddy-config:
```

### c. Create `Caddyfile` in project root

```caddy
chat.yourdomain.com {
    reverse_proxy django-chat:8000
}
```

That's it — Caddy fetches and renews HTTPS certs automatically.

### d. Update `.env` and settings

Add to `.env`:

```ini
CLEARNET_HOST=chat.yourdomain.com
```

Patch [src/djchat/settings.py](src/djchat/settings.py) so it accepts a clearnet host too. Right under the existing `ONION_HOST` block:

```python
_clearnet_host = os.getenv('CLEARNET_HOST', '')
if _clearnet_host:
    ALLOWED_HOSTS.append(_clearnet_host)
    CSRF_TRUSTED_ORIGINS.append(f'https://{_clearnet_host}')
```

Also flip these cookie flags **only when you serve over HTTPS** (clearnet) — they break Tor, which is plain HTTP at the onion layer:

```python
if _clearnet_host:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
```

### e. Bring it up

```bash
docker compose up -d --build
```

Visit `https://chat.yourdomain.com` — should serve the same chat as the onion.

### Running both at once

Tor and Caddy don't conflict: tor publishes onion → django-chat:8000, Caddy publishes domain → django-chat:8000. Same backend, two entrances.

---

## 3. Android: configure `USE_TOR` / `BASE_URL`

Build-time flags live in [android/app/build.gradle.kts](android/app/build.gradle.kts) under `buildTypes`.

| Build type | `USE_TOR` | `BASE_URL` | Used for |
|---|---|---|---|
| `debug` | `false` | `http://10.0.2.2:8000` | Android Studio emulator hitting your local Django |
| `release` | `true` | `http://<your-onion>.onion` | Production install, Tor-only |

### To build a clearnet-only release (Play Store path)

Edit `release` block:

```kotlin
release {
    isMinifyEnabled = true
    proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
    buildConfigField("Boolean", "USE_TOR", "false")
    buildConfigField("String", "BASE_URL", "\"https://chat.yourdomain.com\"")
}
```

### To build a Tor release

Leave the current values (USE_TOR=true, BASE_URL=onion). User must install Orbot.

### Debug on real phone

`10.0.2.2` only works in the emulator. To test debug on a real phone, change debug `BASE_URL` to your PC's LAN IP — e.g. `http://192.168.1.50:8000` (find it with `ipconfig` on Windows / `ip a` on Linux). Phone and PC must be on the same Wi-Fi.

Also: the Django dev server only binds to `127.0.0.1` by default. To accept connections from your phone, run it on `0.0.0.0`:

```bash
python manage.py runserver 0.0.0.0:8000
```

And temporarily add your PC's IP to `ALLOWED_HOSTS` in `settings.py`.

---

## 4. Android: build & sign release APK/AAB

### Generate a keystore (do this once, keep it forever)

```bash
keytool -genkey -v -keystore release.jks -keyalg RSA -keysize 2048 -validity 10000 -alias djangochat
```

**Back this file up.** If you lose it, you can never update your Play Store listing — Google will reject any upload signed with a different key.

Store it outside the repo (e.g. `~/keystores/release.jks`) and **never commit it**.

### Wire signing into Gradle

Create `android/keystore.properties` (gitignored):

```properties
storeFile=/absolute/path/to/release.jks
storePassword=your-store-password
keyAlias=djangochat
keyPassword=your-key-password
```

Add `keystore.properties` to `.gitignore`.

Patch [android/app/build.gradle.kts](android/app/build.gradle.kts):

```kotlin
import java.util.Properties
import java.io.FileInputStream

val keystoreProps = Properties().apply {
    val f = rootProject.file("keystore.properties")
    if (f.exists()) load(FileInputStream(f))
}

android {
    // ... existing config ...

    signingConfigs {
        create("release") {
            if (keystoreProps.containsKey("storeFile")) {
                storeFile = file(keystoreProps["storeFile"] as String)
                storePassword = keystoreProps["storePassword"] as String
                keyAlias = keystoreProps["keyAlias"] as String
                keyPassword = keystoreProps["keyPassword"] as String
            }
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
            // ... rest of release config ...
        }
    }
}
```

### Build commands

```bash
cd android

# Signed APK (sideload, share directly)
./gradlew assembleRelease
# → app/build/outputs/apk/release/app-release.apk

# Signed AAB (Google Play upload)
./gradlew bundleRelease
# → app/build/outputs/bundle/release/app-release.aab

# Debug APK (no signing needed, won't ever go to Play)
./gradlew assembleDebug
# → app/build/outputs/apk/debug/app-debug.apk
```

### Sideload on your phone

```bash
adb install android/app/build/outputs/apk/release/app-release.apk
```

Or copy the APK to the phone and tap it (enable "Install unknown apps" for your file manager first).

### Bump version before each Play Store release

In `build.gradle.kts`:

```kotlin
versionCode = 2     // must increase every upload
versionName = "1.1" // shown to users
```

---

## Play Store notes for the Tor build

Google Play allows Tor apps but they're a moving target — some get pulled, others stay up for years. If you want to publish there, the safer playbook:

1. Ship the **clearnet build** (`USE_TOR=false`, HTTPS URL) as the Play Store version. No Orbot dependency, no Tor mentions in the listing — it's just a normal chat app.
2. Distribute the **Tor build** outside the Play Store (your site, F-Droid, direct APK link).
3. Same codebase, same APK signing key — just different `BASE_URL` build configs.

If you do want a Tor-enabled APK on Play, the safer approach is to make Tor *optional in-app* (settings toggle) rather than required, and not market it as a Tor app.

---

## Quick reference: which build for which scenario

| Scenario | USE_TOR | BASE_URL | Signed? |
|---|---|---|---|
| Local dev on emulator | false | `http://10.0.2.2:8000` | debug auto |
| Local dev on real phone (same Wi-Fi) | false | `http://<PC-LAN-IP>:8000` | debug auto |
| Sideload Tor build | true | `http://<onion>.onion` | release keystore |
| Sideload clearnet build | false | `https://chat.yourdomain.com` | release keystore |
| Play Store upload | false | `https://chat.yourdomain.com` | release keystore (AAB) |
