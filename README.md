# Capture-Coder

An intelligent screen capture and AI-powered coding assistant that automatically solves programming problems by analyzing screenshots and generating optimized solutions.

## 🚀 Features

### Core Functionality
- **Screen Capture**: Capture specific areas or entire windows containing coding problems
- **AI Analysis**: Uses Google's Gemini AI to analyze problem screenshots and generate solutions
- **Iterative Refinement**: Automatically refines solutions through multiple iterations for optimal results
- **Natural Typing**: Types solutions with human-like timing and natural pauses
- **Real-time Feedback**: Apply feedback by copying markdown comments to clipboard

### Capture Modes
- **Area Selection**: Click and drag to select specific problem areas
- **Window Capture**: Automatically capture the active window
- **Clipboard Integration**: Process images copied to clipboard

### Output Options
- **Natural Typing**: Type solutions with realistic human timing
- **Fast Typing**: Rapid typing for quick solutions
- **Manual Control**: Stop typing at any time

### Advanced Features
- **Solution History**: Track all iterations and versions of solutions
- **Refinement Engine**: Continuously improve solutions based on feedback
- **Expert Prompts**: Specialized prompts for competitive programming and software engineering
- **Edge Case Handling**: Comprehensive testing for all edge cases

## 📋 Requirements

- **Operating System**: macOS (uses Quartz for window management)
- **Python**: 3.11 or higher
- **API Key**: Google Gemini API key

## 🛠️ Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd capture-coder
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   Create a `.env` file in the project root:
   ```
   GEMINI_API_KEY=your_google_gemini_api_key_here
   ```

5. **Get a Google Gemini API key**:
   - Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create a new API key
   - Add it to your `.env` file

## 🎯 Usage

### Starting the Application
```bash
python main.py
```

The application runs in the background and listens for keyboard shortcuts.

### Keyboard Shortcuts

#### Capture Commands
- **`Ctrl+Shift+C`**: Start area selection mode
  - Click and drag to select problem area
  - Release to capture and analyze
- **`Ctrl+Shift+W`**: Capture the active window

#### Output Commands
- **`Ctrl+Shift+V`**: Type solution with natural human timing
- **`Ctrl+Shift+F`**: Type solution with fast timing
- **`Ctrl+Shift+X`**: Stop typing immediately

#### Refinement Commands
- **`Ctrl+Shift+R`**: Refine the current solution
- **`Ctrl+Shift+H`**: Show iteration history

### Workflow Example

1. **Capture a Problem**:
   - Press `Ctrl+Shift+C` to start area selection
   - Click and drag to select the coding problem
   - Release to capture and analyze

2. **Review the Solution**:
   - The AI will analyze the problem and generate an optimized solution
   - Solutions go through 3 iterations of refinement

3. **Type the Solution**:
   - Press `Ctrl+Shift+V` for natural typing
   - Press `Ctrl+Shift+F` for fast typing
   - Press `Ctrl+Shift+X` to stop typing

4. **Apply Feedback** (Optional):
   - Copy feedback to clipboard in format: `# fix: your feedback here`
   - The application will automatically apply the feedback and refine the solution

## 🔧 Configuration

### Environment Variables
- `GEMINI_API_KEY`: Your Google Gemini API key (required)

### Customization
The application uses several prompts that can be modified in `main.py`:
- `INITIAL_ANALYSIS_PROMPT`: Initial problem analysis
- `REFINEMENT_PROMPT`: Solution refinement
- `FINAL_OPTIMIZATION_PROMPT`: Final optimization pass
- `USER_FEEDBACK_PROMPT`: User feedback processing

## 📁 Project Structure

```
capture-coder/
├── main.py              # Main application file
├── requirements.txt     # Python dependencies
├── test_tkinter.py     # UI testing utility
├── README.md           # This file
├── .env               # Environment variables (create this)
└── venv/              # Virtual environment
```

## 🧪 Testing

Test the UI overlay functionality:
```bash
python test_tkinter.py
```

This will show a test overlay for 3 seconds to verify the UI components work correctly.

## 🔍 How It Works

### 1. Problem Analysis
- Captures screenshot of coding problem
- Uses Gemini AI to analyze problem type, constraints, and optimal approach
- Generates initial solution with proper imports and edge case handling

### 2. Iterative Refinement
- **Iteration 1**: Initial solution with basic algorithm
- **Iteration 2**: Review for correctness and efficiency
- **Iteration 3**: Final optimization and production-ready code

### 3. Natural Typing
- Simulates human typing patterns with realistic delays
- Includes thinking pauses for complex code structures
- Adjustable speed for different use cases

### 4. Feedback Integration
- Monitors clipboard for markdown comments
- Automatically applies feedback to improve solutions
- Maintains solution history for comparison

## 🚨 Troubleshooting

### Common Issues

**"GEMINI_API_KEY not found"**
- Ensure your `.env` file exists and contains the API key
- Check that the key is valid and has sufficient quota

**Screen capture not working**
- Ensure you have screen recording permissions enabled
- On macOS: System Preferences → Security & Privacy → Privacy → Screen Recording

**Typing not working**
- Ensure the target application accepts keyboard input
- Try using `Ctrl+Shift+X` to stop any ongoing typing

**UI overlay issues**
- Run `python test_tkinter.py` to test UI components
- Ensure you have proper display permissions

### Performance Tips
- Use fast typing (`Ctrl+Shift+F`) for quick solutions
- Use natural typing (`Ctrl+Shift+V`) for demonstrations
- Stop typing (`Ctrl+Shift+X`) if you need to interrupt

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Google Gemini AI**: For providing the AI analysis capabilities
- **pynput**: For keyboard and mouse input handling
- **Pillow**: For image processing and clipboard operations
- **tkinter**: For the UI overlay system

## 📞 Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the code comments in `main.py`
3. Test with `test_tkinter.py` to isolate UI issues
4. Create an issue in the repository

---

**Note**: This application is designed for educational and productivity purposes. Always review and understand the generated code before using it in production environments.
