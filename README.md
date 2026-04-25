# Supply Chain Disruption Predictor

An AI-powered Supply Chain Disruption Analysis Agent that utilizes the Gemini API to perform multi-step automated reasoning. The system monitors supplier footprint, weather risks, geopolitical news, and alternative shipping routes to synthesize full risk assessments.

## Demonstration

Check out the demonstration video to see the agent in action:

<video src="RecordingSupplyChain.mov" width="100%" controls="controls"></video>

[**Click here to download / view the video directly**](./RecordingSupplyChain.mov)

---

## 🛠 Project Structure

- **/backend**: Flask-based Python backend managing API calls, tools execution, and multi-step agentic loop built with `google-genai` SDK.
- **/extension**: Chrome Extension frontend providing a premium visual reasoning interface and interactive UI.

---

## 🚀 How to Run the Project

### 1. Backend Setup (Flask Server)

1. Open your terminal and navigate to the backend folder:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file in the `backend/` directory and add your Gemini API Key:
   ```env
   GEMINI_API_KEY=your_api_key_here
   ```
5. Run the server:
   ```bash
   python app.py
   ```
   > The server will start on `http://localhost:5001`.

### 2. Extension Setup (Chrome Frontend)

1. Open Google Chrome and type `chrome://extensions/` in the URL bar.
2. Toggle on **Developer mode** in the top-right corner.
3. Click the **Load unpacked** button in the top-left corner.
4. Select the `extension/` directory from this project folder.
5. Pinned the new "Supply Chain Predictor" extension in your Chrome toolbar.
6. Open the extension, enter your parameters, and click **Run Agent Analysis**.

---

## 💡 Usage Example

- **Product ID**: `PROD-001` or `PROD-002`
- **Regions**: `East Asia` or `Southeast Asia`
- **Shipping Routes**: `Shanghai to Los Angeles` or `Ho Chi Minh City to Rotterdam`
