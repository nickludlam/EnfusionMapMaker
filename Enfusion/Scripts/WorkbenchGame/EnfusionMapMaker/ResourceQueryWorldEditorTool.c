enum EQComponentSearchMode {
	SUPPLIES,
	VEHICLES
}

enum EQOutputMode {
	CONSOLE,
	FILE
}

[WorkbenchToolAttribute(
	name: "Entity Query Tool",
	description: "Queries the map for resources, inside an AABB, and allows you to reject based on substring of the XOB path",
	wbModules: {"WorldEditor"},
	awesomeFontCode: 0xf6e2)]
class EntityQueryWorldEditorTool: WorldEditorTool
{	
    // Name: Entity Query Tool

	
	////////////////////////////
	// State vars

	World m_currentWorld;
	ref array<IEntity> m_entityResults = null;
	ref array<string> m_excludeStringArray = null;
	
	////////////////////////////
	// Query category

	[Attribute(
		category: "Query",
		desc: "Bounds Min",
		uiwidget: UIWidgets.Coords,
		defvalue: "0 0 0"
	)]
	vector m_queryBoundsMin = Vector(0, 0, 0);

	[Attribute(
		category: "Query",
		desc: "Bounds Max",
		uiwidget: UIWidgets.Coords,
		defvalue: "120000 100 120000"
	)]
	vector m_queryBoundsMax = Vector(0, 0, 0);
	
	
	// Dropdown to set the query enum
	[Attribute(
			category: "Query",
			desc: "Entity component search mode",
			uiwidget: UIWidgets.ComboBox,
			enums: ParamEnumArray.FromEnum(EQComponentSearchMode),
			defvalue: EQComponentSearchMode.SUPPLIES.ToString()
	)]
	EQComponentSearchMode m_componentSearchMode;

	// Dropdown to set the query enum
	[Attribute(
			category: "Query",
			desc: "Entity component query flags",
			uiwidget: UIWidgets.ComboBox,
			enums: ParamEnumArray.FromEnum(EQueryEntitiesFlags),
			defvalue: EQueryEntitiesFlags.ALL.ToString()
	)]
	EQueryEntitiesFlags m_componentQueryFlags;
	
	[Attribute(
		category: "Query",
		desc: "Comma separated path exclusion words (case sensitive)",
		uiwidget: UIWidgets.Auto,
		defvalue: "Tool"
	)]
	string m_exclusionTerms;

	////////////////////////////
	// Output category

	// Dropdown to set the output mode
	[Attribute(
			category: "Output",
			desc: "Output mode",
			uiwidget: UIWidgets.ComboBox,
			enums: ParamEnumArray.FromEnum(EQOutputMode),
			defvalue: EQOutputMode.CONSOLE.ToString()
	)]
	EQOutputMode m_outputMode;
		
	[Attribute("entities.json", UIWidgets.Auto, "Output filename prefix", "", null, "File Output")]
	string m_outputFilename = "entities.json";

	[Attribute("0", UIWidgets.Auto, "Print using a custom formatter", "", null, "Output")]
	bool m_customPrintFormat = false;

	////////////////////////////
	// Buttons

    [ButtonAttribute("Run Query")]
	void RunQuery() {
		if (!BeforeQueryCheck()) {
			Print("Query not possible");
			return;
		}
		
		PrintFormat("Query between %1 and %2 using flags EQueryEntitiesFlags.%3", m_queryBoundsMin, m_queryBoundsMax, EQueryEntitiesFlagsToString(m_componentQueryFlags));		
		bool queryResult = m_currentWorld.QueryEntitiesByAABB(m_queryBoundsMin, m_queryBoundsMax, this.addEntitiesCallback, this.filterEntitiesCallback, m_componentQueryFlags);
		
		if (queryResult) {
			if (m_outputMode == EQOutputMode.FILE) {
				WriteJSONEntityCoordinates();
			} else {
				PrintEntityCoordinates(m_customPrintFormat); // True if you want to modify the printed line, see PrintEntityCoordinates()
			}			
		} else {
			Print("Query failed!");
		}
	}
	
	////////////////////////////
	// Internals
	
	bool BeforeQueryCheck() {
		// Cache world ref
		if (m_currentWorld == null) {
			WorldEditor worldEditor = Workbench.GetModule(WorldEditor);
			WorldEditorAPI api = worldEditor.GetApi();
			m_currentWorld = api.GetWorld();
			if (m_currentWorld == null) {
				Print("GetWorld() returned null!");
				return false;
			}
		}
		
		// Clear previous results
		if (m_entityResults == null) {
			m_entityResults = new array<IEntity>;
		} else {
			m_entityResults.Clear();
		}
		
		// Gather our individual exclusion strings from the comma separated list
        m_excludeStringArray = new array<string>;
		array<string> tmpStringSplit = new array<string>;
		if (m_exclusionTerms.Length() > 0) {
			m_exclusionTerms.Split(",", tmpStringSplit, true);

			// trim them before adding
			foreach(string s: tmpStringSplit) {
				s.TrimInPlace();
				PrintFormat("Adding exclusion string \"%1\"", s);
                m_excludeStringArray.Insert(s);
			}
		}
		
		return true;
	}
	
	bool filterEntitiesCallback(IEntity e) {
		if (m_componentSearchMode == EQComponentSearchMode.SUPPLIES) {
			return filterResourceInventoryEntitiesCallback(e);
		} else if (m_componentSearchMode == EQComponentSearchMode.VEHICLES) {
			return filterAmbientVehicleSpawnEntitiesCallback(e);
		}
		
		return false;
	}
		
	// How we identify the entities which implement in-game supplies
	bool filterResourceInventoryEntitiesCallback(IEntity e) {
    	// Currently we only want to look for objects with resource + inventory components (the supply signposts)
		if (e.FindComponent(SCR_ResourceComponent) && e.FindComponent(InventoryItemComponent)) {
			string xobPath = e.GetVObject().GetResourceName();
            // These also include tool racks, so we want to exclude specific words found in the path
			foreach(string exclusionString : m_excludeStringArray) {
				if (xobPath.Contains(exclusionString)) {
					PrintFormat("Excluding %1 as it contains \"%2\"", xobPath, exclusionString);
					return false;
				}
			}
			
			// default to true for our wanted components
			return true;
		}
		
		return false;
	}
	
	// How we identify the entities which implement a vehicle spawn
	bool filterAmbientVehicleSpawnEntitiesCallback(IEntity e) {
    	// Currently we only want to look for objects with resource + inventory components (the supply signposts)
		if (e.FindComponent(SCR_AmbientVehicleSpawnPointComponent)) {
			return true;
		}
		
		return false;
	}
	
	// Add them all by default
	bool addEntitiesCallback(IEntity e) {
		m_entityResults.Insert(e);
		return true;
	}
	
	// Output to a file. No safety is performed on the filename so be careful when typing!
	void WriteJSONEntityCoordinates() {
		WorldEditor worldEditor = Workbench.GetModule(WorldEditor);
		WorldEditorAPI api = worldEditor.GetApi();

		string filepath = string.Format("$profile:%1", m_outputFilename);
		FileHandle textFileW = FileIO.OpenFile(filepath, FileMode.WRITE);
		if (textFileW) {
			textFileW.WriteLine("[");
			foreach(IEntity foundEntity : m_entityResults) {
				textFileW.WriteLine("{");
				
				vector position = foundEntity.GetOrigin();
				float worldHeight = api.GetTerrainSurfaceY(position[0], position[2]);
				float relativeHeight = position[1] - worldHeight;

				string formattedLocationLine = string.Format("\"locationXZ\": [%1, %2],", position[0], position[2]);
				textFileW.WriteLine(formattedLocationLine);
				
				string formattedHeightLine = string.Format("\"height\": %1", relativeHeight);
				textFileW.WriteLine(formattedHeightLine);

				textFileW.Write("},");
			}
			textFileW.WriteLine("]");
			textFileW.Close();
			
			int entityCount = m_entityResults.Count();
			PrintFormat("Wrote %1 coordinates to %2", entityCount, filepath);
		} else {
			PrintFormat("Failed to open file %1", filepath);
		}
	}
	
	// Just print the results to the console for debugging / checking
	void PrintEntityCoordinates(bool customFormat) {
		WorldEditor worldEditor = Workbench.GetModule(WorldEditor);
		WorldEditorAPI api = worldEditor.GetApi();

		foreach(IEntity foundEntity : m_entityResults) {
			if (customFormat) {
				vector position = foundEntity.GetOrigin();
				
				float worldHeight = api.GetTerrainSurfaceY(position[0], position[2]);
				float relativeHeight = position[1] - worldHeight;
				
				string name = foundEntity.GetName();
				EntityID id = foundEntity.GetID();
				
				Print("-------");
				Print(foundEntity);
				PrintFormat("HEIGHT: %1", relativeHeight);
			} else {
				Print(foundEntity);
			}
		}
		
		int entityCount = m_entityResults.Count();
		PrintFormat("Total entity count: %1", entityCount);
	}
	
	/////////////////////////////
	// Standard tool hooks
	
	override void OnBeforeUnloadWorld() {
		// Remove any cached reference to the world
		m_currentWorld = null;
	}
	
	////////////////////////////
	// Helper functions

    // This will convert the enum value to a string
	string EQueryEntitiesFlagsToString(EQueryEntitiesFlags f)
	{
		typename t = EQueryEntitiesFlags;

		int tVarCount = t.GetVariableCount();
		for (int i = 0; i < tVarCount; i++) {
			EQueryEntitiesFlags value;
			t.GetVariableValue(null, i, value);
			if (value && value == f) {
				return t.GetVariableName(i);
			}
		}

		return "unknown";
	}

	private const int 		TRACE_LAYER_MASK = EPhysicsLayerDefs.Projectile;
	private const float 	MEASURE_INTERVAL = 1.0;
	private const float 	RAY_LENGTH = 3.0;
	private ref array<ref Shape> m_aDbgShapes;

	private void DoTraceLine()
	{
		
		autoptr TraceParam param = new TraceParam;
		//param.Exclude = this;
		param.Flags = TraceFlags.ENTS | TraceFlags.WORLD;
		param.LayerMask = TRACE_LAYER_MASK;
		//param.Start = m_vRCStart;
		//param.End = m_vRCEnd;
		
		TraceResult(param);
	}
	
	private void TraceResult(TraceParam param)
	{
		WorldEditor worldEditor = Workbench.GetModule(WorldEditor);
		WorldEditorAPI api = worldEditor.GetApi();
		BaseWorld world = api.GetWorld();

		float hit = world.TraceMove(param, null);
		
		if (!param.TraceEnt)
			return;

		Print("_____");
		//Print("| " + GetName() + " results" );
		Print("|_ Entity: " + param.TraceEnt);
		Print("|_ Collider: " + param.ColliderName);
		//Print("|_ Material type: " + param.MaterialType);
		Print(" ");
		
		//vector hitPos = m_vRCStart + vector.Forward * (hit * RAY_LENGTH);
		//DBG_Sphere(hitPos, ARGBF(0.5, 1, 0, 0));
	}
	
	private void DBG_Sphere(vector pos, int color)
	{
		vector matx[4];
		Math3D.MatrixIdentity4(matx);
		matx[3] = pos;
		int shapeFlags = ShapeFlags.NOOUTLINE|ShapeFlags.NOZBUFFER|ShapeFlags.TRANSP;
		Shape s = Shape.CreateSphere(color, shapeFlags, pos, 0.05);
		s.SetMatrix(matx);
		//m_aDbgShapes.Insert(s);
	}

}
