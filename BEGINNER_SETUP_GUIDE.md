# 🚀 Complete Beginner's Guide to Running Vancouver Zoning App

## What is Docker and Why Do I Need It?

**Docker** is like a "virtual container" that packages everything needed to run an application. Think of it like a lunch box that contains everything you need for lunch - you don't need to worry about what's inside, just open it and eat!

The Vancouver Zoning App comes in a Docker "container" so you don't need to install Python, databases, or any complicated software. Docker handles all of that for you.

---

## STEP 1: Install Docker Desktop

### **Download Docker Desktop (FREE)**
1. Go to: https://www.docker.com/products/docker-desktop
2. Click the big **"Download for Mac"** or **"Download for Windows"** button
3. Run the installer file that downloads
4. Follow the installation wizard (just click "Next" through everything)
5. **IMPORTANT**: Make sure to check **"Add Docker to PATH"** or **"Install Docker CLI tools"** during installation
   - This lets the simple start/stop scripts work properly
   - If you skip this, you'll have to use the more complicated Docker Desktop GUI method

### **Start Docker Desktop**
1. **On Mac**: Look for Docker in your Applications folder, double-click it
2. **On Windows**: Look for "Docker Desktop" in your Start menu, click it
3. **Wait**: The first time takes a few minutes to start up
4. **Look for**: A whale icon in your system tray (bottom-right on Windows, top-right on Mac)
5. **Success**: When you see "Docker Desktop is running"

---

## STEP 2: Get the Vancouver Zoning App

1. **Download** the `vancouver-zoning-app-docker.zip` file 
2. **Extract/Unzip** it to somewhere easy to find (like your Desktop)
3. **You should see** a folder called `vancouver-zoning-app-docker`

---

## STEP 3: Start the App (3 Easy Ways!)

### **🎯 EASIEST WAY: Double-Click Method**

#### **On Windows:**
1. Open the `vancouver-zoning-app-docker` folder
2. **Double-click** the file called `start.bat`
3. A black window will appear with green text
4. **Wait** for it to say "✅ Application started successfully!"
5. **Done!** Go to Step 4

#### **On Mac:**
1. Open the `vancouver-zoning-app-docker` folder
2. **Right-click** the file called `start.sh`
3. Choose **"Open With" → "Terminal"**
4. **Wait** for it to say "✅ Application started successfully!"
5. **Done!** Go to Step 4

### **🐳 ALTERNATIVE: Using Docker Desktop (Visual)**

1. **Open Docker Desktop** (the whale icon)
2. **Look for "Containers"** in the left sidebar, click it
3. **Click "Create"** or **"Import"** 
4. **Navigate** to your `vancouver-zoning-app-docker` folder
5. **Docker should detect** the project automatically
6. **Click the "Play" button (▶️)** next to "vancouver-zoning-app"
7. **Wait** for the status to show "Running" (green)
8. **Done!** Go to Step 4

---

## STEP 4: Use the App

1. **Open your web browser** (Chrome, Safari, Firefox, Edge - any will work)
2. **Type this address**: `http://localhost:8081`
3. **Press Enter**
4. **You should see**: The Vancouver Zoning App homepage with a search box

### **Test It:**
- Type in an address like: `1055 W Georgia St, Vancouver`
- Click "Search" 
- Wait a few seconds
- You should see a 3D model, satellite image, and zoning information!

---

## STEP 5: When You're Done

### **To Stop the App:**

#### **If you used the double-click method:**
1. Find the `stop.bat` (Windows) or `stop.sh` (Mac) file
2. Double-click it
3. Wait for "✅ Application stopped"

#### **If you used Docker Desktop:**
1. Open Docker Desktop
2. Find "vancouver-zoning-app" in the containers list
3. Click the **"Stop" button (⏹️)**

---

## 🆘 Troubleshooting (If Something Goes Wrong)

### **"Docker is not running" error:**
- Make sure Docker Desktop is open and the whale icon shows "running"
- Try restarting Docker Desktop
- Wait a full minute after starting Docker Desktop

### **"Port 8081 is already in use" error:**
- Something else is using that port
- Try changing 8081 to 8082 in the `docker-compose.yml` file
- Or restart your computer to free up the port

### **Can't access http://localhost:8081:**
- Make sure the app is actually running (check Docker Desktop)
- Try `http://127.0.0.1:8081` instead
- Try a different browser
- Check that you typed the address correctly

### **App is very slow:**
- This is normal the first time (downloading data)
- Make sure you have a good internet connection
- Wait a few minutes and try again

### **Nothing happens when I double-click start.bat/start.sh:**
- Make sure Docker Desktop is running first
- **Check if Docker CLI is installed**: Open Terminal/Command Prompt and type `docker --version`
  - If it says "command not found", you need to reinstall Docker Desktop with CLI tools enabled
  - Or use the Docker Desktop GUI method instead
- Try right-clicking and "Run as Administrator" (Windows)
- Try opening Terminal/Command Prompt manually (see Advanced section below)

---

## 🤓 Advanced: Using Terminal/Command Prompt

If the double-click method doesn't work, you can try the "command line" method:

### **Windows:**
1. Press `Windows key + R`
2. Type `cmd` and press Enter
3. Type: `cd C:\path\to\vancouver-zoning-app-docker` (replace with your actual path)
4. Type: `docker-compose up -d`
5. Press Enter

### **Mac:**
1. Press `Cmd + Space`
2. Type `terminal` and press Enter
3. Type: `cd /path/to/vancouver-zoning-app-docker` (replace with your actual path)
4. Type: `docker-compose up -d`
5. Press Enter

---

## ❓ Frequently Asked Questions

**Q: Do I need to keep Docker Desktop open?**
A: Yes, while using the app. You can minimize it though.

**Q: Is this safe to install?**
A: Yes! Docker Desktop is made by Docker Inc. and used by millions of developers worldwide.

**Q: Will this slow down my computer?**
A: Only while running. When stopped, it uses no resources.

**Q: Can I use this offline?**
A: Partially. The app itself works offline, but it needs internet to fetch live data from Vancouver's servers.

**Q: How much space does this take?**
A: About 2-3 GB when fully installed and running.

**Q: Can I uninstall this easily?**
A: Yes! Just delete the folder and uninstall Docker Desktop like any other program.

---

## 🎯 Summary - What You Just Did

1. ✅ Installed Docker Desktop (like installing a lunch box maker)
2. ✅ Downloaded the Vancouver Zoning App (like getting a pre-made lunch box)
3. ✅ Started the app (like opening the lunch box)
4. ✅ Used the app in your browser (like eating lunch!)

**You are now running a sophisticated geospatial analysis application that would normally require installing dozens of complex software packages!** 🎉

---

*Need more help? The app includes detailed troubleshooting guides and you can always stop and start it again if something goes wrong.*
