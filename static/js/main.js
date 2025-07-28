// File: static/js/main.js
import { initialize as initializeColorService } from './colorService.js';
import { initializeIrvDisplay } from './irvDisplay.js';

document.addEventListener('DOMContentLoaded', () => {
    initializeColorService();
    initializeIrvDisplay();
});
