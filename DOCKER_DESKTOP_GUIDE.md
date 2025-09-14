# 🐳 Docker Desktop Setup Guide

## For Users Who Prefer GUI Over Terminal

### **Prerequisites**
1. **Download Docker Desktop**: https://www.docker.com/products/docker-desktop
2. **Install and start** Docker Desktop
3. **IMPORTANT**: During Docker Desktop installation, make sure to check the option **"Add Docker to PATH"** or **"Install Docker CLI tools"**
   - This allows the start/stop scripts to work properly
   - If you already installed Docker Desktop without this, you may need to reinstall or manually add Docker to your system PATH
4. **Extract** the `vancouver-zoning-app-docker.zip` package

### **Method 1: Using Docker Desktop GUI (Recommended)**

#### **Step 1: Import the Project**
1. Open **Docker Desktop**
2. Click **"Images"** in the left sidebar
3. Look for **"Import"** or **"Load"** button
4. Navigate to your extracted `vancouver-zoning-app-docker` folder
5. Docker Desktop should automatically detect the `docker-compose.yml` file

#### **Step 2: Build and Start**
1. In Docker Desktop, look for **"Compose"** or **"Stacks"** section
2. You should see **"vancouver-zoning-app"** listed
3. Click the **"Play" button (▶️)** to start the application
4. Wait for the status to show **"Running"**

#### **Step 3: Access the Application**
1. Open your web browser
2. Go to: `http://localhost:8081`
3. You should see the Vancouver Zoning App interface

### **Method 2: Using Docker Desktop Terminal**

If the GUI method doesn't work, Docker Desktop has a built-in terminal:

1. In Docker Desktop, click **"Terminal"** tab
2. Navigate to your project folder:
   ```bash
   cd /path/to/vancouver-zoning-app-docker
   ```
3. Run the startup command:
   ```bash
   docker-compose up -d
   ```

### **Managing the Application**

#### **To Stop the Application:**
- In Docker Desktop: Find the container and click **"Stop" (⏹️)**
- Or in terminal: `docker-compose down`

#### **To View Logs:**
- In Docker Desktop: Click on the container name to see logs
- Or in terminal: `docker-compose logs`

#### **To Restart:**
- In Docker Desktop: Click **"Restart" (🔄)**
- Or in terminal: `docker-compose restart`

### **Troubleshooting**

#### **Container won't start:**
1. Check Docker Desktop is running
2. Ensure port 8081 isn't being used by another application
3. Try rebuilding: In Docker Desktop, delete the container and rebuild

#### **Can't access http://localhost:8081:**
1. Check the container status in Docker Desktop shows "Running"
2. Verify the port mapping shows `8081:80`
3. Try `http://127.0.0.1:8081` instead

#### **Build errors:**
1. Make sure you have at least 4GB RAM allocated to Docker
2. Check you have enough disk space (10GB+)
3. Try building with: `docker-compose build --no-cache`

### **Alternative: One-Click Scripts**

If you're comfortable with double-clicking files:
- **Windows**: Double-click `start.bat`
- **Mac/Linux**: Double-click `start.sh` (may need to run in Terminal)

---
*This application provides detailed 3D zoning analysis for Vancouver properties with satellite imagery and development potential calculations.*
