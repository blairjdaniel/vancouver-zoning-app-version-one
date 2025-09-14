import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './FewShotManager.css';

const FewShotManager = ({ onExampleSelect, selectedExamples = [] }) => {
    const [examples, setExamples] = useState([]);
    const [categories, setCategories] = useState({});
    const [loading, setLoading] = useState(false);
    const [activeTab, setActiveTab] = useState('browse');
    const [selectedCategory, setSelectedCategory] = useState('multiplex');
    const [newExample, setNewExample] = useState({
        name: '',
        description: '',
        category: 'multiplex',
        tags: [],
        imageUrl: ''
    });
    const [imageFile, setImageFile] = useState(null);

    useEffect(() => {
        loadExamples();
        loadCategories();
    }, []);

    const loadExamples = async () => {
        try {
            setLoading(true);
            const response = await axios.get('/api/few-shot/examples');
            setExamples(response.data.examples);
        } catch (error) {
            console.error('Error loading examples:', error);
        } finally {
            setLoading(false);
        }
    };

    const loadCategories = async () => {
        try {
            const response = await axios.get('/api/few-shot/categories');
            setCategories(response.data.categories);
        } catch (error) {
            console.error('Error loading categories:', error);
        }
    };

    const handleAddExample = async () => {
        try {
            setLoading(true);
            
            let imageData = null;
            if (imageFile) {
                const reader = new FileReader();
                imageData = await new Promise((resolve) => {
                    reader.onload = () => resolve(reader.result.split(',')[1]);
                    reader.readAsDataURL(imageFile);
                });
            }

            const response = await axios.post('/api/few-shot/add-example', {
                ...newExample,
                image_data: imageData
            });

            if (response.data.success) {
                setNewExample({
                    name: '',
                    description: '',
                    category: 'multiplex',
                    tags: [],
                    imageUrl: ''
                });
                setImageFile(null);
                loadExamples();
            }
        } catch (error) {
            console.error('Error adding example:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleDownloadExample = async () => {
        try {
            setLoading(true);
            const response = await axios.post('/api/few-shot/download-example', {
                url: newExample.imageUrl,
                name: newExample.name,
                category: newExample.category
            });

            if (response.data.success) {
                setNewExample({
                    name: '',
                    description: '',
                    category: 'multiplex',
                    tags: [],
                    imageUrl: ''
                });
                loadExamples();
            }
        } catch (error) {
            console.error('Error downloading example:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleDeleteExample = async (exampleId) => {
        try {
            const response = await axios.delete(`/api/few-shot/delete-example/${exampleId}`);
            if (response.data.success) {
                loadExamples();
            }
        } catch (error) {
            console.error('Error deleting example:', error);
        }
    };

    const handleExampleSelect = (exampleId) => {
        if (onExampleSelect) {
            const isSelected = selectedExamples.includes(exampleId);
            if (isSelected) {
                onExampleSelect(selectedExamples.filter(id => id !== exampleId));
            } else {
                onExampleSelect([...selectedExamples, exampleId]);
            }
        }
    };

    const handleImageUpload = (event) => {
        const file = event.target.files[0];
        if (file) {
            setImageFile(file);
        }
    };

    const filteredExamples = examples.filter(example => 
        selectedCategory === 'all' || example.category === selectedCategory
    );

    return (
        <div className="few-shot-manager">
            <div className="few-shot-header">
                <h3>Few-Shot Learning Examples</h3>
                <div className="tab-buttons">
                    <button 
                        className={activeTab === 'browse' ? 'active' : ''}
                        onClick={() => setActiveTab('browse')}
                    >
                        Browse Examples
                    </button>
                    <button 
                        className={activeTab === 'add' ? 'active' : ''}
                        onClick={() => setActiveTab('add')}
                    >
                        Add Example
                    </button>
                </div>
            </div>

            {activeTab === 'browse' && (
                <div className="browse-section">
                    <div className="category-filter">
                        <label>Filter by Category:</label>
                        <select 
                            value={selectedCategory} 
                            onChange={(e) => setSelectedCategory(e.target.value)}
                        >
                            <option value="all">All Categories</option>
                            {Object.entries(categories).map(([key, value]) => (
                                <option key={key} value={key}>{value}</option>
                            ))}
                        </select>
                    </div>

                    {loading ? (
                        <div className="loading">Loading examples...</div>
                    ) : (
                        <div className="examples-grid">
                            {filteredExamples.map(example => (
                                <div 
                                    key={example.id} 
                                    className={`example-card ${selectedExamples.includes(example.id) ? 'selected' : ''}`}
                                    onClick={() => handleExampleSelect(example.id)}
                                >
                                    {example.image_path && (
                                        <div className="example-image">
                                            <img 
                                                src={`/api/few-shot/examples/${example.id}/image`} 
                                                alt={example.name}
                                                onError={(e) => {
                                                    e.target.style.display = 'none';
                                                }}
                                            />
                                        </div>
                                    )}
                                    <div className="example-info">
                                        <h4>{example.name}</h4>
                                        <p>{example.description}</p>
                                        <div className="example-tags">
                                            <span className="category">{example.category}</span>
                                            {example.tags.map(tag => (
                                                <span key={tag} className="tag">{tag}</span>
                                            ))}
                                        </div>
                                    </div>
                                    <button 
                                        className="delete-btn"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleDeleteExample(example.id);
                                        }}
                                    >
                                        ×
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}

                    {filteredExamples.length === 0 && !loading && (
                        <div className="no-examples">
                            <p>No examples found for this category.</p>
                            <p>Add some examples to get started!</p>
                        </div>
                    )}
                </div>
            )}

            {activeTab === 'add' && (
                <div className="add-section">
                    <div className="form-group">
                        <label>Name:</label>
                        <input
                            type="text"
                            value={newExample.name}
                            onChange={(e) => setNewExample({...newExample, name: e.target.value})}
                            placeholder="Example name"
                        />
                    </div>

                    <div className="form-group">
                        <label>Description:</label>
                        <textarea
                            value={newExample.description}
                            onChange={(e) => setNewExample({...newExample, description: e.target.value})}
                            placeholder="Describe the architectural style, features, etc."
                            rows={3}
                        />
                    </div>

                    <div className="form-group">
                        <label>Category:</label>
                        <select
                            value={newExample.category}
                            onChange={(e) => setNewExample({...newExample, category: e.target.value})}
                        >
                            {Object.entries(categories).map(([key, value]) => (
                                <option key={key} value={key}>{value}</option>
                            ))}
                        </select>
                    </div>

                    <div className="form-group">
                        <label>Tags (comma-separated):</label>
                        <input
                            type="text"
                            value={newExample.tags.join(', ')}
                            onChange={(e) => setNewExample({
                                ...newExample, 
                                tags: e.target.value.split(',').map(tag => tag.trim()).filter(tag => tag)
                            })}
                            placeholder="modern, sustainable, mixed-use"
                        />
                    </div>

                    <div className="form-group">
                        <label>Image Upload:</label>
                        <input
                            type="file"
                            accept="image/*"
                            onChange={handleImageUpload}
                        />
                        {imageFile && (
                            <div className="image-preview">
                                <img 
                                    src={URL.createObjectURL(imageFile)} 
                                    alt="Preview" 
                                    style={{maxWidth: '200px', maxHeight: '200px'}}
                                />
                            </div>
                        )}
                    </div>

                    <div className="form-group">
                        <label>Or Image URL:</label>
                        <input
                            type="url"
                            value={newExample.imageUrl}
                            onChange={(e) => setNewExample({...newExample, imageUrl: e.target.value})}
                            placeholder="https://example.com/image.jpg"
                        />
                    </div>

                    <div className="form-actions">
                        <button 
                            onClick={handleAddExample}
                            disabled={loading || !newExample.name || !newExample.description}
                        >
                            {loading ? 'Adding...' : 'Add Example'}
                        </button>
                        {newExample.imageUrl && (
                            <button 
                                onClick={handleDownloadExample}
                                disabled={loading || !newExample.name}
                            >
                                {loading ? 'Downloading...' : 'Download from URL'}
                            </button>
                        )}
                    </div>
                </div>
            )}

            {selectedExamples.length > 0 && (
                <div className="selected-examples">
                    <h4>Selected Examples ({selectedExamples.length})</h4>
                    <div className="selected-list">
                        {selectedExamples.map(exampleId => {
                            const example = examples.find(e => e.id === exampleId);
                            return example ? (
                                <span key={exampleId} className="selected-tag">
                                    {example.name}
                                    <button onClick={() => handleExampleSelect(exampleId)}>×</button>
                                </span>
                            ) : null;
                        })}
                    </div>
                </div>
            )}
        </div>
    );
};

export default FewShotManager; 