import React, { useState, useEffect } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js';

/**
 * Hugging Face Pipeline Viewer Component
 * 
 * This component integrates with the HF text-to-3D pipeline to generate
 * 3D architectural models from design prompts. It provides:
 * - Model selection and validation
 * - Generation progress tracking
 * - 3D model visualization
 * - Export capabilities
 */
function HFPipelineViewer({ 
  selectedVariant, 
  parcel, 
  zoning, 
  siteConfig,
  onModelGenerated 
}) {
  const [availableModels, setAvailableModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('shap-e');
  const [outputFormat, setOutputFormat] = useState('glb');
  const [quality, setQuality] = useState('medium');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [generatedModel, setGeneratedModel] = useState(null);
  const [error, setError] = useState(null);
  const [modelInfo, setModelInfo] = useState({});

  // Load available models on component mount
  useEffect(() => {
    loadAvailableModels();
  }, []);

  // Load model info when selected model changes
  useEffect(() => {
    if (selectedModel) {
      loadModelInfo(selectedModel);
    }
  }, [selectedModel]);

  const loadAvailableModels = async () => {
    try {
      const response = await fetch('/api/hf/models');
      const data = await response.json();
      
      if (data.models) {
        setAvailableModels(Object.keys(data.models));
        setModelInfo(data.models);
      }
    } catch (error) {
      console.error('Error loading available models:', error);
      setError('Failed to load available models');
    }
  };

  const loadModelInfo = async (modelName) => {
    try {
      const response = await fetch('/api/hf/validate-model', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ model_name: modelName }),
      });
      
      const data = await response.json();
      if (data.valid) {
        setModelInfo(prev => ({ ...prev, [modelName]: data.info }));
      }
    } catch (error) {
      console.error('Error validating model:', error);
    }
  };

  const generate3DModel = async () => {
    if (!selectedVariant || !parcel || !zoning) {
      setError('Please select a variant and ensure parcel/zoning data is available');
      return;
    }

    setIsGenerating(true);
    setGenerationProgress(0);
    setError(null);

    try {
      // Prepare site data
      const siteData = {
        lot_area: siteConfig?.lot_dimensions?.lot_area || 0,
        lot_frontage: siteConfig?.lot_dimensions?.lot_frontage || 0,
        lot_depth: siteConfig?.lot_dimensions?.lot_depth || 0,
        address: parcel?.properties?.address || 'Unknown'
      };

      // Prepare zoning data
      const zoningData = {
        ZONING_DISTRICT: zoning.ZONING_DISTRICT,
        FAR: zoning.FAR,
        max_height: zoning.max_height,
        coverage: zoning.coverage,
        front: zoning.front,
        side: zoning.side,
        rear: zoning.rear
      };

      const requestData = {
        prompt: selectedVariant.prompt,
        variant_id: selectedVariant.id,
        site_data: siteData,
        zoning_data: zoningData,
        model_name: selectedModel,
        output_format: outputFormat,
        quality: quality,
        seed: Math.floor(Math.random() * 1000000) // Random seed
      };

      // Simulate progress updates
      const progressInterval = setInterval(() => {
        setGenerationProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return prev;
          }
          return prev + 10;
        });
      }, 2000);

      const response = await fetch('/api/hf/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
      });

      clearInterval(progressInterval);
      setGenerationProgress(100);

      const data = await response.json();

      if (data.success) {
        // Convert base64 model data back to binary
        const modelData = data.model_data ? 
          Uint8Array.from(atob(data.model_data), c => c.charCodeAt(0)) : null;

        const modelResult = {
          data: modelData,
          format: data.model_format,
          metadata: data.metadata,
          generationTime: data.generation_time,
          variantId: selectedVariant.id,
          modelName: selectedModel
        };

        setGeneratedModel(modelResult);
        
        if (onModelGenerated) {
          onModelGenerated(modelResult);
        }
      } else {
        setError(data.error || 'Generation failed');
      }
    } catch (error) {
      console.error('Error generating 3D model:', error);
      setError('Failed to generate 3D model');
    } finally {
      setIsGenerating(false);
      setGenerationProgress(0);
    }
  };

  const downloadModel = () => {
    if (!generatedModel || !generatedModel.data) {
      return;
    }

    const blob = new Blob([generatedModel.data], { 
      type: `model/${generatedModel.format}` 
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${selectedVariant.id}_${selectedModel}.${generatedModel.format}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const renderModelPreview = () => {
    if (!generatedModel) return null;

    return (
      <div style={{
        border: '1px solid #ddd',
        borderRadius: '8px',
        padding: '15px',
        marginTop: '15px',
        backgroundColor: '#f8f9fa'
      }}>
        <h4 style={{ margin: '0 0 10px 0', color: '#333' }}>
          Generated 3D Model
        </h4>
        
        <div style={{ fontSize: '12px', color: '#666', marginBottom: '10px' }}>
          <div><strong>Model:</strong> {generatedModel.modelName}</div>
          <div><strong>Format:</strong> {generatedModel.format}</div>
          <div><strong>Generation Time:</strong> {generatedModel.generationTime?.toFixed(1)}s</div>
          <div><strong>Variant:</strong> {generatedModel.variantId}</div>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={downloadModel}
            style={{
              padding: '8px 16px',
              backgroundColor: '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '12px'
            }}
          >
            Download Model
          </button>
          
          <button
            onClick={() => setGeneratedModel(null)}
            style={{
              padding: '8px 16px',
              backgroundColor: '#6c757d',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '12px'
            }}
          >
            Clear
          </button>
        </div>
      </div>
    );
  };

  const renderProgressBar = () => {
    if (!isGenerating) return null;

    return (
      <div style={{
        marginTop: '15px',
        padding: '15px',
        backgroundColor: '#e3f2fd',
        borderRadius: '8px',
        border: '1px solid #bbdefb'
      }}>
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          marginBottom: '10px'
        }}>
          <span style={{ fontSize: '14px', fontWeight: 'bold', color: '#1976d2' }}>
            Generating 3D Model...
          </span>
          <span style={{ fontSize: '12px', color: '#666' }}>
            {generationProgress}%
          </span>
        </div>
        
        <div style={{
          width: '100%',
          height: '8px',
          backgroundColor: '#e0e0e0',
          borderRadius: '4px',
          overflow: 'hidden'
        }}>
          <div style={{
            width: `${generationProgress}%`,
            height: '100%',
            backgroundColor: '#1976d2',
            transition: 'width 0.3s ease'
          }} />
        </div>
        
        <div style={{ 
          fontSize: '11px', 
          color: '#666', 
          marginTop: '5px',
          fontStyle: 'italic'
        }}>
          This may take 2-5 minutes depending on model complexity
        </div>
      </div>
    );
  };

  if (!selectedVariant) {
    return (
      <div style={{
        padding: '20px',
        textAlign: 'center',
        color: '#666',
        fontStyle: 'italic'
      }}>
        Please select a variant to generate 3D model
      </div>
    );
  }

  return (
    <div style={{ padding: '20px' }}>
      <h3 style={{ margin: '0 0 20px 0', color: '#333' }}>
        Hugging Face 3D Model Generation
      </h3>

      {/* Model Selection */}
      <div style={{ marginBottom: '20px' }}>
        <h4 style={{ margin: '0 0 10px 0', color: '#333' }}>Model Configuration</h4>
        
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
          {/* Model Selection */}
          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontSize: '12px', fontWeight: 'bold' }}>
              Model:
            </label>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              style={{
                width: '100%',
                padding: '8px',
                border: '1px solid #ced4da',
                borderRadius: '4px',
                fontSize: '12px'
              }}
              disabled={isGenerating}
            >
              {availableModels.map(model => (
                <option key={model} value={model}>
                  {model} {modelInfo[model]?.available ? '✓' : '✗'}
                </option>
              ))}
            </select>
          </div>

          {/* Output Format */}
          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontSize: '12px', fontWeight: 'bold' }}>
              Output Format:
            </label>
            <select
              value={outputFormat}
              onChange={(e) => setOutputFormat(e.target.value)}
              style={{
                width: '100%',
                padding: '8px',
                border: '1px solid #ced4da',
                borderRadius: '4px',
                fontSize: '12px'
              }}
              disabled={isGenerating}
            >
              <option value="glb">GLB (Recommended)</option>
              <option value="obj">OBJ</option>
              <option value="ply">PLY</option>
            </select>
          </div>

          {/* Quality */}
          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontSize: '12px', fontWeight: 'bold' }}>
              Quality:
            </label>
            <select
              value={quality}
              onChange={(e) => setQuality(e.target.value)}
              style={{
                width: '100%',
                padding: '8px',
                border: '1px solid #ced4da',
                borderRadius: '4px',
                fontSize: '12px'
              }}
              disabled={isGenerating}
            >
              <option value="low">Low (Fast)</option>
              <option value="medium">Medium (Balanced)</option>
              <option value="high">High (Slow)</option>
            </select>
          </div>

          {/* Generate Button */}
          <div style={{ display: 'flex', alignItems: 'end' }}>
            <button
              onClick={generate3DModel}
              disabled={isGenerating}
              style={{
                width: '100%',
                padding: '10px',
                backgroundColor: isGenerating ? '#6c757d' : '#28a745',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: isGenerating ? 'not-allowed' : 'pointer',
                fontSize: '12px',
                fontWeight: 'bold'
              }}
            >
              {isGenerating ? 'Generating...' : 'Generate 3D Model'}
            </button>
          </div>
        </div>
      </div>

      {/* Model Info */}
      {modelInfo[selectedModel] && (
        <div style={{
          marginBottom: '20px',
          padding: '10px',
          backgroundColor: '#f8f9fa',
          borderRadius: '4px',
          fontSize: '11px'
        }}>
          <strong>Model Info:</strong> {modelInfo[selectedModel].model_id}
          <br />
          <strong>Supported Formats:</strong> {modelInfo[selectedModel].supported_formats?.join(', ')}
          <br />
          <strong>Status:</strong> {modelInfo[selectedModel].available ? 'Available' : 'Unavailable'}
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div style={{
          marginBottom: '15px',
          padding: '10px',
          backgroundColor: '#f8d7da',
          border: '1px solid #f5c6cb',
          borderRadius: '4px',
          color: '#721c24',
          fontSize: '12px'
        }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Progress Bar */}
      {renderProgressBar()}

      {/* Generated Model Preview */}
      {renderModelPreview()}

      {/* Variant Info */}
      <div style={{
        marginTop: '20px',
        padding: '15px',
        backgroundColor: '#f8f9fa',
        borderRadius: '8px',
        border: '1px solid #dee2e6'
      }}>
        <h4 style={{ margin: '0 0 10px 0', color: '#333' }}>Selected Variant</h4>
        <div style={{ fontSize: '12px', color: '#666' }}>
          <div><strong>Name:</strong> {selectedVariant.name}</div>
          <div><strong>ID:</strong> {selectedVariant.id}</div>
          <div><strong>Description:</strong> {selectedVariant.description}</div>
          {selectedVariant.metadata && (
            <div style={{ marginTop: '5px' }}>
              <strong>Parameters:</strong>
              <ul style={{ margin: '5px 0', paddingLeft: '20px' }}>
                {Object.entries(selectedVariant.metadata).map(([key, value]) => (
                  <li key={key}>
                    {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}: {value}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default HFPipelineViewer; 