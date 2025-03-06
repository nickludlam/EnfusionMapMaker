[WorkbenchToolAttribute(name: "Auto Camera Screenshot", description: "Automatically create screenshots of an area of a map.", wbModules: {"WorldEditor"}, awesomeFontCode: 0xf447)]
class AutoCameraScreenshotWorldEditorTool: WorldEditorTool
{
    // Name: Auto Camera Screenshot Tool
    // Author: Bewilderbeest <bewilder@recoil.org>

    // This is a WORLD EDITOR tool, so open up your required map first.

    // Since we cannot fully control the camera in the World Editor,
    // this requires the user to set the FOV to 15, and the farPlane
    // distance to ~ 5000. This script will yield incorrect results
    // otherwise!

    // The camera will start at m_StartCoords and step by m_StepSize
    // in each axis until it reaches m_EndCoordsX, generating
    // screenshots into your $profile directory, which is usually
    // C:\Users\<NAME>\Documents\My Games\ArmaReforgerWorkbench\profile\

    // This screenshot capture process has been tested by me to work
    // when you fullscreen the editor application using F11. So to
    // start the process, press the "Start Capture" button, then
    // immediately hit F11 to go into full screen mode, and this
    // gives a consistent screenshot size, otherwise changes to the
    // camera window size will mess with the output.

    // In order to account for LOD streaming and exposure changes,
    // There is a small sleep delay after the camera has moved, and
    // then a small delay after the screenshot has been triggered
    // to allow for async operations to complete. These might need
    // tuning if your screenshots are discontinuous or inconsistent

    // During capture, the escape key will allow you to stop the process,
    // because you cannot access the button if the editor camera is full screen!

    
    [Attribute("200 0 200", UIWidgets.Coords, "Camera start", "", null, "Camera Movement")]
    vector m_StartCoords;
    
    [Attribute("12800 0 12800", UIWidgets.Coords, "Camera end", "", null, "Camera Movement")]
    vector m_EndCoords;
    
    [Attribute("950", UIWidgets.Auto, "Camera height", "", null, "Camera Movement")]
    int m_CameraHeight;
    
    [Attribute("0", UIWidgets.CheckBox, "Camera height is absolute, not relative to terrain height", "", null, "Camera Movement")]
    bool m_AbsoluteCameraHeight;

    [Attribute("100", UIWidgets.Auto, "Camera step size", "", null, "Camera Movement")]
    int m_StepSize;

    [Attribute("700", UIWidgets.Auto, "Sleep after incremental camera movement (ms)", "", null, "Timing")]
    float m_MoveSleep;

    [Attribute("2000", UIWidgets.Auto, "Sleep after a large amount of camera movement (ms)", "", null, "Timing")]
    float m_DiscontinuousMoveSleep;

    [Attribute("200", UIWidgets.Auto, "Sleep after screenshot call (ms)", "", null, "Timing")]
    float m_ScreenshotSleep;
    
    [Attribute("mapoutput", UIWidgets.Auto, "Output filename predix", "", null, "Screenshot output")]
    string m_outputDirectory;
    
    [Attribute("eden", UIWidgets.Auto, "Output filename predix", "", null, "Screenshot output")]
    string m_outputFilePrefix;

    [Attribute("_tile.png", UIWidgets.Auto, "Tile filename suffix (must match the python code)", "", null, "Advanced")]
    string m_tileFilenameSuffix;

    // Loop state
    private bool m_InCaptureLoop;
    private bool m_CancelCurrentLoop;
    
    [ButtonAttribute("Position Camera")]
    void PositionCamera() {
        MoveCamera(m_StartCoords[0], m_StartCoords[2], m_CameraHeight, m_AbsoluteCameraHeight);
    }
    
    [ButtonAttribute("Stop Capture")]
    void StopCapture()
    {
        if (m_InCaptureLoop) {
            if (m_CancelCurrentLoop) {
                Print("Halt in progress");
            } else {
                m_CancelCurrentLoop = true;
            }
            Print("Halting capture loop ...");
        } else {
            Print("No capture loop running");
        }
    }
    
    // Delete all button
    [ButtonAttribute("Start Capture")]
    void StartCapture()	
    {
        if (m_InCaptureLoop) {
            Print("Capture loop already in progress");
            return;
        }
        
        m_InCaptureLoop = true;
        m_CancelCurrentLoop = false;
        
        Print("Performing initial camera move");
        MoveCamera(m_StartCoords[0], m_StartCoords[2], m_CameraHeight, m_AbsoluteCameraHeight);

        for (int i = 0; i < 5; i++) {
            Print("Starting capture in " + (5 - i) + " seconds");
            Sleep(1000);

            // Early out here after the sleep, in case the user already aborted the loop
            if (m_CancelCurrentLoop) {
                m_InCaptureLoop = false;
                Print("Capture loop aborted");
                return;
            }
        }
        
        int xDistance = m_EndCoords[0] - m_StartCoords[0];
        int zDistance = m_EndCoords[2] - m_StartCoords[2];
        
        int stepCountX = xDistance / m_StepSize;
        int stepCountZ = zDistance / m_StepSize;
        
        Print("Starting capture loop");
        DoLoop(m_StartCoords[0], m_StartCoords[2], m_StepSize, m_CameraHeight, stepCountX, stepCountZ);
        Print("Finished capture");
    }
    
    override void OnDeActivate()
    {
        m_CancelCurrentLoop = true;
    }
    
    // We loop over Z inside X, so we travel vertically in strips, slowly crossing right. Z is North, X is East.
    void DoLoop(int initialX, int initialZ, int stepSize, int camHeight, int stepCountX, int stepCountZ) {		
        string outputDirectory = "$profile:" + m_outputDirectory;
        PrintFormat("Making directory %1", outputDirectory);
        
        bool cameraDiscontinuousMovement = false;

        bool done = false;
                
        for (int x = 0; x < stepCountX; x++) {
            float mapPositionX = initialX + (x * stepSize);
            int intMapPositionX = mapPositionX;
            
            // We use the x coordinate for the output directory structure
            string xCoordinateDir = outputDirectory + "/" + string.Format("%1", intMapPositionX) + "/";
            PrintFormat("Making directory %1", xCoordinateDir);
            FileIO.MakeDirectory(xCoordinateDir);
            
            cameraDiscontinuousMovement = true; // this happens after each loop

            for (int z = 0; z < stepCountZ; z++) {
                float mapPositionZ = initialZ + (z * stepSize);
                int intMapPositionZ = mapPositionZ;
                
                // Make the output hashdir structure first
                string outputPath = xCoordinateDir + m_outputFilePrefix + "_" + intMapPositionX + "_" + intMapPositionZ; // it will automatically add .png
                string outputPathWithSuffix = outputPath + ".png";
                
                if (FileIO.FileExist(outputPathWithSuffix)) {
                    PrintFormat("Screenshot already exists at %1", outputPathWithSuffix);
                    cameraDiscontinuousMovement = true; // we have broken the incremental movements
                    continue;
                }
            
                // check for the cropped tile version
                string tilePath = outputPath + m_tileFilenameSuffix;
                if (FileIO.FileExist(tilePath)) {
                    // Skip!
                    PrintFormat("Skipping completed tile %1", tilePath);
                    cameraDiscontinuousMovement = true; // we have broken the incremental movements
                    continue;
                } else {
                    PrintFormat("No existing tile found at %1", tilePath);
                }
                
                PrintFormat("Moving to x=%1/%2, z=%3/%4", x, stepCountX, z, stepCountZ);
                MoveCamera(mapPositionX, mapPositionZ, camHeight, m_AbsoluteCameraHeight);
                if (cameraDiscontinuousMovement) {
                    Sleep(m_DiscontinuousMoveSleep);
                    cameraDiscontinuousMovement = false;
                } else {
                    Sleep(m_MoveSleep);
                }
                
                // Now create the screenshot
                PrintFormat("Writing PNG to %1", outputPath);
                bool success = System.MakeScreenshot(outputPath);
                if (!success) {
                    Print("Failed to write screenshot");
                    m_CancelCurrentLoop = true;
                }
                // Wait for the screenshot to write
                Sleep(m_ScreenshotSleep);

                // Break if we've been asked to				
                if (m_CancelCurrentLoop) {
                    break;
                }
            }
            
            // Break if we've been asked to				
            if (m_CancelCurrentLoop) {
                break;
            }			
        }
        
        // Move the camera back to the initial position
        MoveCamera(initialX, initialZ, camHeight, m_AbsoluteCameraHeight);

        m_InCaptureLoop = false;
    }
    
    void MoveCamera(float xPos, float zPos, float camHeight, bool camHeightAbsolute)
    {
        float height = 0;
        WorldEditor worldEditor = Workbench.GetModule(WorldEditor);
        WorldEditorAPI api = worldEditor.GetApi();
        api.TryGetTerrainSurfaceY(xPos, zPos, height);
        
        if (camHeightAbsolute) {
            height = camHeight;
        } else {
            height += camHeight;
        }
        
        vector newCamPos = Vector(xPos, height, zPos);
        vector lookVec = Vector(0, -90, 0); // Somehow the X and Y coords are different between the GUI representation and the code repr
        api.SetCamera(newCamPos, lookVec);
    }

    
    // Method called on keyboard key press
    override void OnKeyPressEvent(KeyCode key, bool isAutoRepeat)
    {
        // Abort on esc
        if (key == KeyCode.KC_ESCAPE && isAutoRepeat == false && m_InCaptureLoop && m_CancelCurrentLoop == false)
        {
            m_CancelCurrentLoop = true;
        }		
    }

}