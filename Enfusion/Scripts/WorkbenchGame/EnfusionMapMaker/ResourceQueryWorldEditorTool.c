[WorkbenchToolAttribute(name: "Entity Query Tool", description: "Queries the map for resources, inside an AABB, and allows you to reject based on substring of the XOB path", wbModules: {"WorldEditor"}, awesomeFontCode: 0xf6e2)]
class EntityQueryWorldEditorTool: WorldEditorTool
{
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
		defvalue: "4000 0 4000"
	)]
	vector m_queryBoundsMin = Vector(0, 0, 0);

	[Attribute(
		category: "Query",
		desc: "Bounds Max",
		uiwidget: UIWidgets.Coords,
		defvalue: "5000 0 5000"
	)]
	vector m_queryBoundsMax = Vector(0, 0, 0);
	
	// Dropdown to set the query enum
	[Attribute(
			category: "Query",
			desc: "Entity query flags",
			uiwidget: UIWidgets.ComboBox,
			enums: ParamEnumArray.FromEnum(EQueryEntitiesFlags),
			defvalue: EQueryEntitiesFlags.ALL.ToString()
	)]
	EQueryEntitiesFlags m_queryFlags;
	
	[Attribute(
		category: "Query",
		desc: "Comma separated exclusion words (case sensitive)",
		uiwidget: UIWidgets.Auto,
		defvalue: "Tool"
	)]
	string m_commaSeparatedExclusionString;

	////////////////////////////
	// Output category

	[Attribute("0", UIWidgets.Auto, "Write output file", "", null, "File Output")]
	bool m_writeFile = false;
	
	[Attribute("entities.json", UIWidgets.Auto, "Output filename prefix", "", null, "File Output")]
	string m_outputFilename = "entities.json";

	////////////////////////////
	// Buttons

    [ButtonAttribute("Run Query")]
	void RunQuery() {
		if (!BeforeQueryCheck()) {
			Print("Query not possible");
			return;
		}
		
		PrintFormat("Query between %1 and %2 using flags EQueryEntitiesFlags.%3", m_queryBoundsMin, m_queryBoundsMax, EQueryEntitiesFlagsToString(m_queryFlags));		
		bool queryResult = m_currentWorld.QueryEntitiesByAABB(m_queryBoundsMin, m_queryBoundsMax, this.addEntitiesCallback, this.filterResourceEntitiesCallback, m_queryFlags);
		if (queryResult) {
			// Two main modes of operation
			if (m_writeFile) {
				WriteJSONEntityCoordinates();
			} else {
				PrintResults(false); // True if you want to modify the printed line, see PrintResults()
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
		
		// Gather our exclusion strings
		m_excludeStringArray = new array<string>;
		if (m_commaSeparatedExclusionString.Length() > 0) {
			PrintFormat("Collecting exclusion terms from %1", m_commaSeparatedExclusionString);
			m_commaSeparatedExclusionString.Split(",", m_excludeStringArray, true);

			// trim them
			foreach(string s: m_excludeStringArray) {
				s.TrimInPlace();
				PrintFormat("Exclusion string %1", s);
			}
		}
		
		return true;
	}
		
	// Currently we only want to look for resource + inventory (the signposts)
	bool filterResourceEntitiesCallback(IEntity e) {
		if (e.FindComponent(SCR_ResourceComponent) && e.FindComponent(InventoryItemComponent)) {
			string xobPath = e.GetVObject().GetResourceName();
			foreach(string exclusionString : m_excludeStringArray) {
				if (xobPath.Contains(exclusionString)) {
					PrintFormat("Excluding %1 as it contains %2", xobPath, exclusionString);
					return false;
				}
			}
			
			// default to true for our wanted components
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
		string filepath = string.Format("$profile:%1", m_outputFilename);
		FileHandle textFileW = FileIO.OpenFile(filepath, FileMode.WRITE);
		if (textFileW) {
			textFileW.WriteLine("[");
			foreach(IEntity foundEntity : m_entityResults) {
				vector position = foundEntity.GetOrigin();
				string formattedLine = string.Format(" [%1, %2],", position[0], position[2]);
				textFileW.WriteLine(formattedLine);
			}
			textFileW.WriteLine("]");
			textFileW.Close();
			
			int entityCount = m_entityResults.Count();
			PrintFormat("Wrote %1 coordinates", entityCount);
		} else {
			PrintFormat("Failed to open file %1", filepath);
		}
	}
	
	// Just print the results to the console for debugging / checking
	void PrintResults(bool customFormat) {
		foreach(IEntity foundEntity : m_entityResults) {
			if (customFormat) {
				vector position = foundEntity.GetOrigin();
				string name = foundEntity.GetName();
				string formattedLine = string.Format("%1 => %2, %3,", name, position[0], position[2]);
				Print(formattedLine);
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

	
}
