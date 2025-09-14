import React, { useState, useRef, useEffect } from 'react';
import './AIChat.css';

const AIChat = ({ selectedAddressData, onImageGenerated }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: 'ai',
      content: "Hi! I'm TOAD your Vancouver zoning AI assistant. Ask me about zoning rules, heritage requirements, or building possibilities!",
      timestamp: new Date().toISOString()
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showImageOptions, setShowImageOptions] = useState(false);
  const [conversationKey, setConversationKey] = useState(null); // Store conversation key for image generation
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);

  const handleSendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: input,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // Debug logging to see what data we have
      console.log("🔍 AIChat Debug - selectedAddressData:", selectedAddressData);
      console.log("🔍 AIChat Debug - selectedAddressData.properties:", selectedAddressData?.properties);
      console.log("🔍 AIChat Debug - Zoning paths check:");
      console.log("  - selectedAddressData.current_zoning:", selectedAddressData?.current_zoning);
      console.log("  - selectedAddressData.properties?.current_zoning:", selectedAddressData?.properties?.current_zoning);
      console.log("  - selectedAddressData.zoning_district:", selectedAddressData?.zoning_district);
      console.log("  - selectedAddressData.api_response?.properties?.current_zoning:", selectedAddressData?.api_response?.properties?.current_zoning);
      
      // Build context from current address data
      const context = selectedAddressData ? {
        address: selectedAddressData.civic_address || selectedAddressData.full_address,
        zoning: {
          current_zoning: (() => {
            // Check multiple possible zoning data locations
            console.log("🔍 Checking zoning paths:");
            console.log("  - selectedAddressData.current_zoning:", selectedAddressData?.current_zoning);
            console.log("  - selectedAddressData.properties?.current_zoning:", selectedAddressData?.properties?.current_zoning);
            console.log("  - selectedAddressData.properties?.calculated_building_metrics:", selectedAddressData?.properties?.calculated_building_metrics);
            console.log("  - selectedAddressData.properties?.building_metrics:", selectedAddressData?.properties?.building_metrics);
            console.log("  - selectedAddressData.calculated_building_metrics:", selectedAddressData?.calculated_building_metrics);
            console.log("  - selectedAddressData.zoning_district:", selectedAddressData?.zoning_district);
            
            const zoning = selectedAddressData.current_zoning || 
                          selectedAddressData.properties?.current_zoning || 
                          selectedAddressData.properties?.calculated_building_metrics?.zoning_district ||
                          selectedAddressData.properties?.building_metrics?.zoning_district ||
                          selectedAddressData.calculated_building_metrics?.zoning_district ||
                          selectedAddressData.zoning_district ||
                          selectedAddressData.api_response?.properties?.current_zoning;
            
            console.log("🎯 Final zoning value found:", zoning);
            // Filter out invalid zoning values but also check if it's literally "Unknown"
            if (zoning && zoning !== 'Unknown' && zoning !== 'N/A' && zoning !== '' && zoning !== null) {
              return zoning;
            }
            
            // If no valid zoning found, let's try to infer from building metrics
            const buildingMetrics = selectedAddressData?.properties?.building_metrics || selectedAddressData?.properties?.calculated_building_metrics;
            if (buildingMetrics?.zoning_district) {
              console.log("🎯 Found zoning in building metrics:", buildingMetrics.zoning_district);
              return buildingMetrics.zoning_district;
            }
            
            return null;
          })(),
          site_area: selectedAddressData.site_area || selectedAddressData.properties?.site_area,
          max_height: selectedAddressData.max_height || 
                     selectedAddressData.properties?.zoning_building_metrics?.max_height ||
                     selectedAddressData.properties?.calculated_building_metrics?.height_max_allowed ||
                     selectedAddressData.calculated_building_metrics?.height_max_allowed,
          setbacks: selectedAddressData.setbacks || 
                   selectedAddressData.properties?.zoning_setbacks || 
                   selectedAddressData.properties?.setbacks ||
                   selectedAddressData.properties?.calculated_setbacks ||
                   selectedAddressData.calculated_setbacks,
          FAR: selectedAddressData.FAR || 
              selectedAddressData.properties?.zoning_building_metrics?.FAR || 
              selectedAddressData.properties?.building_metrics?.FAR ||
              selectedAddressData.properties?.calculated_building_metrics?.FAR ||
              selectedAddressData.calculated_building_metrics?.FAR,
          coverage: selectedAddressData.coverage || 
                   selectedAddressData.properties?.zoning_building_metrics?.coverage || 
                   selectedAddressData.properties?.building_metrics?.coverage ||
                   selectedAddressData.properties?.calculated_building_metrics?.coverage ||
                   selectedAddressData.calculated_building_metrics?.coverage,
          // Add more comprehensive zoning data
          lot_type: selectedAddressData.lot_type || selectedAddressData.properties?.lot_type,
          ocp_designation: selectedAddressData.ocp_designation || selectedAddressData.properties?.ocp_designation,
          zoning_conditions: selectedAddressData.zoning_conditions || selectedAddressData.properties?.zoning_conditions,
          // Add building metrics from site analysis
          calculated_setbacks: selectedAddressData.properties?.setbacks,
          calculated_building_metrics: selectedAddressData.properties?.building_metrics,
          // Add zoning rules from lookup
          zoning_setbacks: selectedAddressData.properties?.zoning_setbacks,
          zoning_building_metrics: selectedAddressData.properties?.zoning_building_metrics,
          // Add development conditions and constraints
          development_conditions: selectedAddressData.properties?.development_conditions,
          enclosure_status: selectedAddressData.properties?.enclosure_status,
          potential_lane_dedication: selectedAddressData.properties?.potential_lane_dedication,
          potential_street_widening: selectedAddressData.properties?.potential_street_widening
        },
        heritage: {
          heritage_designation: selectedAddressData.heritage_designation || selectedAddressData.properties?.heritage_designation,
          nearby_heritage_sites: selectedAddressData.heritage_data?.nearby_heritage_sites || selectedAddressData.properties?.heritage_data?.nearby_heritage_sites || [],
          // Also check for direct heritage info
          is_heritage_designated: selectedAddressData.heritage_designation?.is_heritage_designated || selectedAddressData.properties?.heritage_designation?.is_heritage_designated,
          building_name: selectedAddressData.heritage_designation?.building_name || selectedAddressData.properties?.heritage_designation?.building_name,
          category: selectedAddressData.heritage_designation?.category || selectedAddressData.properties?.heritage_designation?.category
        },
        infrastructure: selectedAddressData.api_response?.properties?.infrastructure_analysis || {}
      } : {};

      console.log("🔍 AIChat Debug - context being sent:", context);

      const response = await fetch('/api/ai/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: input,
          context: context
        }),
      });

      const result = await response.json();

      if (result.success) {
        const aiMessage = {
          id: Date.now() + 1,
          type: 'ai',
          content: result.response,
          timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, aiMessage]);

        // Store conversation key if image generation is suggested
        if (result.suggests_image_generation && result.conversation_key) {
          setConversationKey(result.conversation_key);
          console.log('🎨 Stored conversation key for image generation:', result.conversation_key);
        }

        // Check if the user asked about building design/visualization or if AI suggests it
        if (result.suggests_image_generation || 
            input.toLowerCase().includes('design') || 
            input.toLowerCase().includes('building') || 
            input.toLowerCase().includes('render') ||
            input.toLowerCase().includes('image') ||
            input.toLowerCase().includes('modular') ||
            input.toLowerCase().includes('visualization')) {
          setShowImageOptions(true);
        }
      } else {
        throw new Error(result.error || 'Failed to get AI response');
      }
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage = {
        id: Date.now() + 1,
        type: 'ai',
        content: `Sorry, I encountered an error: ${error.message}. Please try again.`,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleGenerateImage = async (useConversationPrompt = true) => {
    if (!selectedAddressData) {
      alert('Please select an address first to generate building images.');
      return;
    }

    setIsLoading(true);
    setShowImageOptions(false);

    try {
      // If we have a conversation key, use conversation-based prompt generation
      if (conversationKey && useConversationPrompt) {
        console.log('🎨 Using conversation-based DALL-E prompt generation');
        
        const requestBody = {
          conversation_key: conversationKey,
          dalle_prompt_override: "generate_from_conversation"
        };

        const response = await fetch('/api/ai/generate-building', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(requestBody),
        });

        const result = await response.json();

        if (result.success) {
          // Add image message to chat
          const imageMessage = {
            id: Date.now(),
            type: 'ai',
            content: `Here's your AI-generated building visualization based on our conversation:`,
            image: result.image_data,
            imageUrl: result.image_url,
            prompt: result.prompt_used,
            timestamp: new Date().toISOString()
          };
          setMessages(prev => [...prev, imageMessage]);

          // Callback to parent component
          if (onImageGenerated) {
            onImageGenerated(result);
          }
        } else {
          throw new Error(result.error || 'Failed to generate image from conversation');
        }
      } else {
        // Fallback to old method if no conversation context
        console.log('🎨 Fallback to traditional design params method');
        
        const requestBody = {
          design_params: {
            building_type: 'single-family house',
            style: 'modern_residential'
          },
          parcel_data: selectedAddressData.api_response || selectedAddressData
        };
        
        if (conversationKey) {
          requestBody.conversation_key = conversationKey;
        }

        const response = await fetch('/api/ai/generate-building', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(requestBody),
        });

        const result = await response.json();

        if (result.success) {
          // Add image message to chat
          const imageMessage = {
            id: Date.now(),
            type: 'ai',
            content: `Here's a building design visualization for ${selectedAddressData.civic_address || selectedAddressData.full_address}:`,
            image: result.image_data,
            imageUrl: result.image_url,
            prompt: result.prompt_used,
            timestamp: new Date().toISOString()
          };
          setMessages(prev => [...prev, imageMessage]);

          // Callback to parent component
          if (onImageGenerated) {
            onImageGenerated(result);
          }
        } else {
          throw new Error(result.error || 'Failed to generate image');
        }
      }
    } catch (error) {
      console.error('Image generation error:', error);
      const errorMessage = {
        id: Date.now(),
        type: 'ai',
        content: `Sorry, I couldn't generate the building image: ${error.message}`,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const quickQuestions = [
    "What can I build on this property?",
    "What are the setback requirements?", 
    "Is this property heritage designated?",
    "Show me building design options",
    "What's the maximum building height?",
    "Are there any infrastructure constraints?"
  ];

  return (
    <>
      {/* Chat Toggle Button */}
      <button
        className={`ai-chat-toggle ${isOpen ? 'open' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className="chat-icon">🤖</span>
        <span className="chat-label">AI Assistant</span>
        {!isOpen && (
          <span className="chat-notification">💬</span>
        )}
      </button>

      {/* Chat Window */}
      {isOpen && (
        <div className="ai-chat-window">
          <div className="ai-chat-header">
            <div className="chat-title">
              <span className="chat-icon">🤖</span>
              <span>TOAD</span>
            </div>
            <button 
              className="chat-close"
              onClick={() => setIsOpen(false)}
            >
              ✕
            </button>
          </div>

          <div className="ai-chat-messages">
            {messages.map((message) => (
              <div key={message.id} className={`message ${message.type}`}>
                <div className="message-content">
                  {message.image ? (
                    <div className="image-message">
                      <p>{message.content}</p>
                      <img 
                        src={`data:image/png;base64,${message.image}`} 
                        alt="Generated building design"
                        className="generated-image"
                      />
                      <small className="image-prompt">
                        Generated from: {message.prompt}
                      </small>
                    </div>
                  ) : (
                    <div className="text-message">
                      {message.content}
                    </div>
                  )}
                  <small className="message-time">
                    {formatTime(message.timestamp)}
                  </small>
                </div>
              </div>
            ))}
            
            {/* Image Generation Options */}
            {showImageOptions && !isLoading && (
              <div className="message ai">
                <div className="message-content">
                  <div className="image-options">
                    {conversationKey ? (
                      // Conversation-based generation
                      <>
                        <p>🎨 I can generate a building visualization based on our conversation!</p>
                        <div className="image-option-buttons">
                          <button onClick={() => handleGenerateImage(true)} className="primary-button">
                            ✨ Generate from Conversation
                          </button>
                          <button onClick={() => handleGenerateImage(false)} className="secondary-button">
                            🏗️ Use Basic Style
                          </button>
                          <button onClick={() => setShowImageOptions(false)} className="cancel-button">
                            ❌ Cancel
                          </button>
                        </div>
                      </>
                    ) : (
                      // Fallback for when no conversation context
                      <>
                        <p>Would you like me to generate a building design visualization?</p>
                        <div className="image-option-buttons">
                          <button onClick={() => handleGenerateImage(false)}>
                            Generate Building
                          </button>
                          <button onClick={() => setShowImageOptions(false)}>
                            ❌ Cancel
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>
            )}

            {isLoading && (
              <div className="message ai">
                <div className="message-content">
                  <div className="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick Questions */}
          <div className="quick-questions">
            {quickQuestions.map((question, index) => (
              <button
                key={index}
                className="quick-question"
                onClick={() => {
                  setInput(question);
                  setTimeout(handleSendMessage, 100);
                }}
                disabled={isLoading}
              >
                {question}
              </button>
            ))}
          </div>

          <div className="ai-chat-input">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask about zoning rules, heritage requirements, or building possibilities..."
              disabled={isLoading}
              rows="2"
            />
            <button 
              onClick={handleSendMessage}
              disabled={!input.trim() || isLoading}
              className="send-button"
            >
              {isLoading ? '⏳' : '📤'}
            </button>
          </div>

          <div className="ai-chat-footer">
            <small>
              🤖 AI Assistant • Powered by GPT-4 & DALL-E 3
              {selectedAddressData && (
                <span> • Analyzing: {selectedAddressData.civic_address || selectedAddressData.full_address}</span>
              )}
            </small>
          </div>
        </div>
      )}
    </>
  );
};

export default AIChat;
