# 🤖 AI Assistant Setup Guide

The Vancouver Zoning Viewer includes a powerful AI assistant that can:
- Answer zoning questions in natural language
- Generate building design visualizations 
- Provide design recommendations based on site constraints
- Create architectural renderings using DALL-E 3

## 🔧 **Setup Instructions**

### **Step 1: Get OpenAI API Key**

1. Go to [OpenAI Platform](https://platform.openai.com)
2. Sign up or log in to your account  
3. Navigate to **API Keys** section
4. Click **"Create new secret key"**
5. Copy the API key (starts with `sk-...`)

**Cost Estimate:**
- Text chat: ~$0.03 per 1,000 tokens (very affordable)
- Image generation: ~$0.04 per image with DALL-E 3
- Typical usage: $10-50/month for regular use

### **Step 2: Configure the Application**

1. In your vancouver-zoning-app-client folder, copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file and add your OpenAI API key:
   ```
   OPENAI_API_KEY=sk-your-actual-api-key-here
   ```

3. Save the file

### **Step 3: Restart the Application**

```bash
# Stop the current application
docker-compose down

# Rebuild with AI capabilities
docker-compose build --no-cache

# Start with AI enabled
docker-compose up -d
```

## 🎯 **AI Features Overview**

### **1. Zoning Chat Assistant** 🗣️
- **Natural Language Queries**: "What can I build on this lot?"
- **Context Awareness**: Knows current address and zoning data
- **Expert Knowledge**: Vancouver zoning bylaws and heritage rules
- **Quick Questions**: Pre-defined common queries

**Example Conversations:**
```
User: "Is this property heritage designated?"
AI: "Yes, this property at 212 E 38TH AV is heritage designated as the 
     Lawson-Logie House (Category C). This means any alterations must 
     be compatible with the heritage character..."

User: "What are my setback requirements?"
AI: "Based on your RS-1 zoning, you need: Front: 4.5m, Side: 1.5m, 
     Rear: 4.0m. Your 1,503m² lot provides ample space for these setbacks..."
```

### **2. Building Design Generator** 🏠
- **Automatic Style Detection**: Heritage vs Modern based on context
- **Site-Specific Design**: Uses actual lot dimensions and constraints
- **Multiple Variations**: Modern, Heritage-Compatible, Traditional
- **Professional Quality**: High-resolution architectural renderings

**Generated Images Include:**
- Contextual neighborhood setting
- Zoning-compliant building envelopes
- Appropriate architectural styles
- Realistic lighting and materials
- Vancouver-specific design elements

### **3. Smart Design Suggestions** 💡
- **Contextual Recommendations**: Based on heritage status, lot size
- **Zoning Compliance**: Ensures designs meet all requirements
- **Style Guidance**: Heritage compatibility vs modern options
- **Optimization**: Maximize building potential within constraints

## 🚀 **Usage Examples**

### **Text Chat Examples:**
```
"Show me building design options for this lot"
"What's the maximum height I can build?"
"Are there any heritage restrictions?"
"What infrastructure might affect my development?"
"How do I maximize density while staying compliant?"
```

### **Image Generation Triggers:**
- Asking about "design", "building", "render", "visualization"
- Clicking quick-action buttons for design variations
- Requesting "show me what I can build"

### **Design Variations Available:**
1. **🏠 Auto Style**: AI chooses best style based on context
2. **🏢 Modern**: Contemporary design with clean lines
3. **🏛️ Heritage Compatible**: Respectful of heritage designation
4. **🏘️ Traditional Duplex**: Maximizing density traditionally
5. **🏡 Laneway House**: Secondary dwelling options

## 💰 **Cost Management**

### **Typical Usage Costs:**
- **Text Queries**: $0.01-0.05 per conversation
- **Image Generation**: $0.04 per image
- **Monthly Estimate**: $10-50 for regular professional use

### **Cost Control Tips:**
1. **Use Quick Questions**: Pre-defined queries are efficient
2. **Batch Image Requests**: Generate multiple variations at once
3. **Monitor Usage**: OpenAI dashboard shows spending
4. **Set Limits**: Configure spending limits in OpenAI account

## 🔒 **Security & Privacy**

### **Data Handling:**
- API calls are encrypted (HTTPS)
- No persistent storage of conversations
- OpenAI processes requests but doesn't train on your data
- Property addresses sent to AI for context (required for accuracy)

### **API Key Security:**
- Store API key in `.env` file (never in code)
- Don't share API keys
- Rotate keys periodically
- Monitor usage for unusual activity

## 🛠 **Troubleshooting**

### **AI Not Working:**
```
# Check AI status endpoint
curl http://localhost:8081/api/ai/status

# Check logs for errors
docker-compose logs -f vancouver-zoning-app
```

### **Common Issues:**

**❌ "OpenAI API key not configured"**
- Solution: Add `OPENAI_API_KEY` to `.env` file and restart

**❌ "Failed to generate image"**
- Check: API key is valid and has credits
- Check: Internet connection for OpenAI API calls

**❌ "Chat not responding"**
- Check: Docker container is running
- Check: Browser console for errors
- Try: Refresh page and retry

## 🎨 **Advanced Features**

### **Custom Prompts:**
The AI system uses sophisticated prompts that include:
- Current property zoning data
- Heritage designation status  
- Infrastructure constraints
- Lot geometry and dimensions
- Neighborhood context

### **Few-Shot Learning:**
The system includes pre-trained examples for:
- Vancouver heritage architecture
- RS-1/RT zoning typical designs
- Laneway house configurations
- Modern vs traditional styles

### **Future Enhancements:**
- Voice interface for hands-free queries
- PDF report generation with AI insights
- Integration with permit probability predictions
- Cost estimation integration
- Multiple design variations in single request

---

## 🎯 **Getting Started Checklist**

- [ ] Obtain OpenAI API key
- [ ] Configure `.env` file with API key
- [ ] Restart Docker application
- [ ] Test AI chat with simple question
- [ ] Try generating building image
- [ ] Set up usage monitoring in OpenAI dashboard

**🚀 Once configured, your Vancouver Zoning Viewer becomes a powerful AI-enhanced urban planning platform that will impress clients and streamline your workflow!**
