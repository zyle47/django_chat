plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.djangochat.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.djangochat.app"
        minSdk = 21
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"

        buildConfigField("String", "ONION_URL", "\"http://6vn7felaig4gmcf5fex6pdjw56zd3hrzpocaoeuk5oewckvjxs7n5eyd.onion\"")
    }

    buildFeatures {
        buildConfig = true
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("info.guardianproject.netcipher:netcipher:2.1.0")
    implementation("info.guardianproject.netcipher:netcipher-webkit:2.1.0")
}
