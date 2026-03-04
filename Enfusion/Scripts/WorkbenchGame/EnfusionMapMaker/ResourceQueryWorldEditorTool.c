enum EQComponentSearchMode {
	SUPPLY_CACHE,
	CAMPAIGN_SUPPLIES,
	VEHICLE,
	VEHICLE_REPAIR,
	VEHICLE_REFUEL,
	MOB_SPAWN,
	CAPTURE_POINT,
	CONTROL_POINT,
	RADIO_RELAY
}

enum EQOutputMode {
	CONSOLE,
	CONSOLE_DEBUG,
	FILE
}

// We generate our own map of this data as the methods in
// SCR_CampaignSourceBaseComponent are protected!?
class CampaignSuppliesInformation {
	string m_sName;
	int m_iIncome;
	int m_iArrivalTime;

	// A simple constructor makes insertion much cleaner
    void CampaignSuppliesInformation(string name, int income, int arrivalTime)
    {
        m_sName = name;
        m_iIncome = income;
        m_iArrivalTime = arrivalTime;
    }
}


[WorkbenchToolAttribute(
	name: "Entity Query Tool",
	description: "Queries the map for resources, inside an AABB, and allows you to reject based on substring of the XOB path. A Single Query will use the selected search mode. A Batch Query will run all of them.",
	wbModules: {"WorldEditor"},
	awesomeFontCode: 0xf6e2)]
class EntityQueryWorldEditorTool: WorldEditorTool
{	
	// Name: Entity Query Tool
	
	////////////////////////////
	// State vars

	World m_currentWorld;
	ref array<IEntity> m_entityResults = new array<IEntity>;
	ref array<string> m_excludeStringArray = new array<string>;
	
	ref array<ref CampaignSuppliesInformation> m_campaignSuppliesInformation = new array<ref CampaignSuppliesInformation>();
	
	////////////////////////////
	// Query category

	[Attribute(
		category: "Query",
		desc: "Bounds Min",
		uiwidget: UIWidgets.Coords,
		defvalue: "0 -500 0"
	)]
	vector m_queryBoundsMin = Vector(0, 0, 0);

	[Attribute(
		category: "Query",
		desc: "Bounds Max",
		uiwidget: UIWidgets.Coords,
		defvalue: "160000 1000 160000"
	)]
	vector m_queryBoundsMax = Vector(0, 0, 0);
	
	
	// Dropdown to set the query enum
	[Attribute(
			category: "Query",
			desc: "Entity component search mode",
			uiwidget: UIWidgets.ComboBox,
			enums: ParamEnumArray.FromEnum(EQComponentSearchMode),
			defvalue: EQComponentSearchMode.SUPPLY_CACHE.ToString()
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
		
	[Attribute("everon_conflict", UIWidgets.Auto, "Output filename prefix (usually map + game mode)", "", null, "File Output")]
	string m_outputFilePrefix = "everon_conflict";

	////////////////////////////
	// Buttons

	[ButtonAttribute("Run Batch Query")]
	void RunBatchQuery() {
		if (!BeforeQueryCheck()) {
			Print("Query not possible");
			return;
		}
		
		EQComponentSearchMode originalValue = m_componentSearchMode;
		
		// Now loop over all our EQComponentSearchMode
		typename t = EQComponentSearchMode;
		int tVarCount = t.GetVariableCount();
		for (int i = 0; i < tVarCount; i++) {
			EQComponentSearchMode searchMode;
			if (t.GetVariableValue(null, i, searchMode)) {
				m_componentSearchMode = searchMode; // Override the chosen search mode
				QueryAndOutput();
			}
		}
		
		m_componentSearchMode = originalValue;
	}

	[ButtonAttribute("Run Single Query")]
	void RunSingleQuery() {
		if (!BeforeQueryCheck()) {
			Print("Query not possible");
			return;
		}
		
		QueryAndOutput();
	}

	// [ButtonAttribute("Debug")]
	// void Debug() {

	// 	//proto external int GetSelectedEntitiesCount();
	// 	//proto external IEntitySource GetSelectedEntity(int n = 0);
	// 	WorldEditor worldEditor = Workbench.GetModule(WorldEditor);
	// 	WorldEditorAPI api = worldEditor.GetApi();
	// 	m_currentWorld = api.GetWorld();

	// 	int selectedEntityCount = api.GetSelectedEntitiesCount();
	// 	for (int i = 0; i < selectedEntityCount; i++) {
	// 		IEntitySource sourceEntity = api.GetSelectedEntity(i);
	// 		IEntity selectEntity = api.SourceToEntity(sourceEntity);
	// 		Print("Name: " + selectEntity.GetName());
	// 		string niceName = api.GetEntityNiceName(sourceEntity);
	// 		Print("Nice name: " + niceName);
	// 		ResourceName prefabPathSource = SCR_ResourceNameUtils.GetPrefabName(selectEntity);
	// 		Print("Path: " + prefabPathSource);
	// 	}
	// }
	
	////////////////////////////
	// Internals
	
	void QueryAndOutput()
	{
        // First clear the results of the last query
   		m_entityResults.Clear();

		PrintFormat("Query between %1 and %2 using flags EQueryEntitiesFlags.%3", m_queryBoundsMin, m_queryBoundsMax, EQueryEntitiesFlagsToString(m_componentQueryFlags));		
		bool queryResult = m_currentWorld.QueryEntitiesByAABB(m_queryBoundsMin, m_queryBoundsMax, this.addEntitiesCallback, this.filterEntitiesCallback, m_componentQueryFlags);
		
		if (queryResult) {
			if (m_outputMode == EQOutputMode.FILE) {
				WriteEntitesToFile();
			} else {
				PrintEntities();
			}
		} else {
			typename t = EQComponentSearchMode;
			PrintFormat("Query failed for mode %1", GetCurrentSearchModeName());
		}
	}
	
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
			PrintFormat("Got world %1", m_currentWorld);
		}
		
		// Ensure we have our supplies info defined
		PopulateCampaignSuppliesInformation();
				
		// Gather our individual exclusion strings from the comma separated list
		m_excludeStringArray.Clear();
		
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
		if (m_componentSearchMode == EQComponentSearchMode.SUPPLY_CACHE) {
			return filterResourceInventoryEntitiesCallback(e);
		} else if (m_componentSearchMode == EQComponentSearchMode.CAMPAIGN_SUPPLIES) {
			return filterCampaignSuppliesEntitiesCallback(e);
		} else if (m_componentSearchMode == EQComponentSearchMode.VEHICLE) {
			return filterAmbientVehicleSpawnEntitiesCallback(e);
		} else if (m_componentSearchMode == EQComponentSearchMode.VEHICLE_REPAIR) {
			return filterVehicleRepairEntitiesCallback(e);
		} else if (m_componentSearchMode == EQComponentSearchMode.VEHICLE_REFUEL) {
			return filterRefuelEntitiesCallback(e);
		} else if (m_componentSearchMode == EQComponentSearchMode.MOB_SPAWN) {
			return filterMOBSpawnEntitiesCallback(e);
		} else if (m_componentSearchMode == EQComponentSearchMode.CAPTURE_POINT) {
			return filterRegularCapturePointEntitiesCallback(e);
		} else if (m_componentSearchMode == EQComponentSearchMode.CONTROL_POINT) {
			return filterControlPointEntitiesCallback(e);
		} else if (m_componentSearchMode == EQComponentSearchMode.RADIO_RELAY) {
			return filterRadioRelayEntitiesCallback(e);
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

	// How we identify the entities which implement in-game supplies
	bool filterCampaignSuppliesEntitiesCallback(IEntity e) {
		// Currently we only want to look for objects with resource + inventory components (the supply signposts)
		if (e.FindComponent(SCR_CampaignSuppliesComponent) && e.FindComponent(SCR_CampaignMilitaryBaseComponent)) {
			SCR_CampaignMilitaryBaseComponent cmbComponent = SCR_CampaignMilitaryBaseComponent.Cast(e.FindComponent(SCR_CampaignMilitaryBaseComponent));			
			if (cmbComponent.GetType() == SCR_ECampaignBaseType.SOURCE_BASE) {
				return true;
			}
		}
		
		return false;
	}
	
	// How we identify the entities which implement a vehicle spawn
	bool filterAmbientVehicleSpawnEntitiesCallback(IEntity e) {
		if (e.FindComponent(SCR_AmbientVehicleSpawnPointComponent)) {
			return true;
		}
		
		return false;
	}
	
	bool filterVehicleRepairEntitiesCallback(IEntity e) {
		if (e.FindComponent(SCR_RepairSupportStationComponent)) {
			return true;
		}
		
		return false;
	}
	
	bool filterRefuelEntitiesCallback(IEntity e) {
		if (e.FindComponent(SCR_FuelSupportStationComponent) || e.FindComponent(SCR_FuelManagerComponent)) {
			return true;
		}
		
		return false;
	}
	
	bool filterMilitaryBase(IEntity e, bool canBeHQ, bool isControlPoint, bool isRadioRelay) {
		if (e.FindComponent(SCR_CampaignMilitaryBaseComponent)) {
			SCR_CampaignMilitaryBaseComponent base = SCR_CampaignMilitaryBaseComponent.Cast(e.FindComponent(SCR_CampaignMilitaryBaseComponent));
			if (!isRadioRelay && base.GetType() == SCR_ECampaignBaseType.BASE) {
				// If it can be an HQ, the control point status is irrelevant
				if (canBeHQ && base.CanBeHQ()) {
					return true;
				} else if (!canBeHQ && !base.CanBeHQ() && base.IsControlPoint() == isControlPoint) {
					return true;
				}
			} else if (isRadioRelay && base.GetType() == SCR_ECampaignBaseType.RELAY) {
				return true;
			}
		}
		return false;
	}

	bool filterMOBSpawnEntitiesCallback(IEntity e) {
		return filterMilitaryBase(e, true, false, false);
	}
	
	bool filterRegularCapturePointEntitiesCallback(IEntity e) {
		return filterMilitaryBase(e, false, false, false);
	}
	
	bool filterControlPointEntitiesCallback(IEntity e) {
		return filterMilitaryBase(e, false, true, false);
	}
	
	bool filterRadioRelayEntitiesCallback(IEntity e) {
		return filterMilitaryBase(e, false, false, true);
	}
	
	
	// Add them all by default
	bool addEntitiesCallback(IEntity e) {
		m_entityResults.Insert(e);
		return true;
	}
	
	// Output to a file. No safety is performed on the filename so be careful when typing!
	void WriteEntitesToFile() {
		WorldEditor worldEditor = Workbench.GetModule(WorldEditor);
		WorldEditorAPI api = worldEditor.GetApi();
		
		// Early out if there's no entities in the query results
		if (m_entityResults.Count() == 0) {
			PrintFormat("Skipping zero entity results for mode %1", GetCurrentSearchModeName());
			return;
		}

		string filepath = string.Format("$profile:%1", GetFilenameForMode());
		FileHandle textFileW = FileIO.OpenFile(filepath, FileMode.WRITE);
		if (textFileW) {
			textFileW.Write(CollectAllObjectJSON());
			textFileW.Close();
			
			int entityCount = m_entityResults.Count();
			PrintFormat("Wrote %1 coordinates to %2", entityCount, filepath);
		} else {
			PrintFormat("Failed to open file %1", filepath);
		}
	}
	
	// Just print the results to the console for debugging / checking
	void PrintEntities() {
		WorldEditor worldEditor = Workbench.GetModule(WorldEditor);
		WorldEditorAPI api = worldEditor.GetApi();
		
		if (m_outputMode == EQOutputMode.CONSOLE_DEBUG)
		{
			// If we're in debug printing mode, run each entity through a function to output console info
			foreach(IEntity entity : m_entityResults) {
				CustomPrintEntity(entity, api);
			}
		} else {
			Print(CollectAllObjectJSON());
		}
		
		int entityCount = m_entityResults.Count();
		PrintFormat("Total entity count: %1", entityCount);
	}
	
	// Custom entity printing where we can get additional information and explore the API
	void CustomPrintEntity(IEntity entity, WorldEditorAPI api) {
		vector position = entity.GetOrigin();
		float worldHeight = api.GetTerrainSurfaceY(position[0], position[2]);
		float relativeHeight = position[1] - worldHeight;
						
		bool entityResourcesInfinite;
		float entityTotalResources;
		GetResourceAttributes(entity, entityResourcesInfinite, entityTotalResources);
		
		Print("-------");
		Print(entity);
        Print("  NAME: " + entity.GetName());
	
		IEntitySource entitySource = api.EntityToSource(entity);
		Print("  NICE NAME: " + api.GetEntityNiceName(entitySource));
		
		ResourceName prefabPathSource = SCR_ResourceNameUtils.GetPrefabName(entity);
		Print("  PREFAB PATH: " + prefabPathSource);
		PrintFormat("  HEIGHT: %1", relativeHeight);
		if (entityResourcesInfinite) {
			PrintFormat("  RESOURCES: INFINITE");
		} else {
			PrintFormat("  RESOURCES: %1", entityTotalResources);
		}
	}

	// For SUPPLY_CACHE, we can find the amount of supplies
	void GetResourceAttributes(IEntity resourceEntity, out bool infiniteResources, out float totalResourceValue) {
		float totalChildResources = CountResourcesInChildren(resourceEntity);
		PrintFormat("Direct resources: %1", totalChildResources);
		
		IEntity parent = resourceEntity.GetParent();
		if (!parent) {
			Print("No parent!", LogLevel.ERROR);
			return;
		}
		
		bool isInfinite;
		if (FindInfiniteContainer(parent, isInfinite)) {
			float totalParentResources = CountResourcesInChildren(parent);
			PrintFormat("  Found %1 supplies on parent!", totalParentResources);
			Print("  Found on PARENT");

			infiniteResources = isInfinite;
			totalResourceValue = totalParentResources;
			return;
		}
		
		IEntity resourceSibling = parent.GetChildren();
		while (resourceSibling)
		{
			if (FindInfiniteContainer(resourceSibling, isInfinite)) {
				
				float totalResources = CountResourcesInChildren(resourceSibling);
				PrintFormat("  Found %1 supplies on sibling!", totalResources);
				Print("  Found on SIBLING");

				infiniteResources = isInfinite;
				totalResourceValue = totalResources;

				return;
			}
			
			resourceSibling = resourceSibling.GetSibling();
		}
	}
	
	bool FindInfiniteContainer(IEntity targetEntity, out bool containerIsInfinite) {
		SCR_ResourceComponent targetResourceComp = SCR_ResourceComponent.Cast(targetEntity.FindComponent(SCR_ResourceComponent));
		SCR_SlotCompositionComponent targetSlotCompComp = SCR_SlotCompositionComponent.Cast(targetEntity.FindComponent(SCR_SlotCompositionComponent));
		if (targetResourceComp && targetSlotCompComp) {
			PrintFormat("  Container: %1", targetEntity);
			SCR_ResourceContainer targetContainer;
			if (targetResourceComp.GetContainer(EResourceType.SUPPLIES, targetContainer)) {
				bool isInfinite = targetContainer.IsResourceGainEnabled();
				PrintFormat("    isInfinite %1", isInfinite);
				containerIsInfinite = isInfinite;
			} else {
				Print("Didn't find our virtual container!", LogLevel.ERROR);
			}
			return true;
		}
		
		return false;
	}
	
	float CountResourcesInChildren(IEntity parent) {
		float totalResourceCount = 0;
		IEntity resourceSibling = parent.GetChildren();
		while (resourceSibling)
		{
			SCR_ResourceComponent targetResourceComp = SCR_ResourceComponent.Cast(resourceSibling.FindComponent(SCR_ResourceComponent));
			if (targetResourceComp) {
				SCR_ResourceContainer targetContainer;
				if (targetResourceComp.GetContainer(EResourceType.SUPPLIES, targetContainer)) {
					float resourceValue = targetContainer.GetResourceValue();
					float maxResourceValue = targetContainer.GetMaxResourceValue();
					PrintFormat("    adding resourceValue %1 / %2 from %3", resourceValue, maxResourceValue, targetContainer);
					totalResourceCount += resourceValue;
				} else {
					Print("Didn't find our container!", LogLevel.ERROR);
				}
			}

			resourceSibling = resourceSibling.GetSibling();
		}
		
		return totalResourceCount;
	}
	
	
	/////////////////////////////
	// Standard tool hooks
	
	override void OnBeforeUnloadWorld() {
		Print("World unloading, clearing cached world reference and results");
		// Remove any cached reference to the world
		m_currentWorld = null;
	}
	
	override void OnDeActivate() {
		Print("Deactivating tool and clearing results");
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
	
	// Output formatting
	
	string MakeObjectJSONStart()
	{
		return "  {\n";
	}
	
	string MakeObjectJSONEnd()
	{
		return "\n  }";
	}
	
    // This does not output a trailing comma or newline
	string MakeObjectJSONCommon(IEntity entity)
	{
	    WorldEditor worldEditor = Workbench.GetModule(WorldEditor);
        WorldEditorAPI api = worldEditor.GetApi();

		string outputString = "";
		
		// Type
		typename t = EQComponentSearchMode;
		outputString += string.Format("    \"mapLocationType\": \"%1\",\n", t.GetVariableName(m_componentSearchMode));
		
		// Name
		string name = entity.GetName();
		if (name.Length() == 0) {
			IEntitySource entitySource = api.EntityToSource(entity);
			// Try the nice name
			name = api.GetEntityNiceName(entitySource);
		}
		
		string formattedNameLine = string.Format("    \"name\": \"%1\",", name);
		outputString += formattedNameLine + "\n";

		// LocationXZ
		vector position = entity.GetOrigin();
		string formattedLocationLine = string.Format("    \"locationXZ\": [%1, %2],", position[0], position[2]);
		outputString += formattedLocationLine + "\n";

		// Height
		float worldHeight = api.GetTerrainSurfaceY(position[0], position[2]);
		float relativeHeight = position[1] - worldHeight;

		string formattedHeightLine = string.Format("    \"height\": %1", relativeHeight);
		outputString += formattedHeightLine;

		return outputString;
	}
	
	string MakeObjectJSONSupplyCache(IEntity entity)
	{
		// Resource values
		bool entityResourcesInfinite;
		float entityTotalResources;
		GetResourceAttributes(entity, entityResourcesInfinite, entityTotalResources);
		
		float resourcesAvailable = entityTotalResources;
		if (entityResourcesInfinite) { resourcesAvailable = -1; }
		string formattedResourcesAvailableLine = string.Format("    \"suppliesAvailable\": %1", resourcesAvailable);
		return formattedResourcesAvailableLine;
	}
	
	string MakeObjectJSONCampaignSupplies(IEntity entity)
	{
		ResourceName prefabPathSource = SCR_ResourceNameUtils.GetPrefabName(entity);
		// Now loop through m_campaignSuppliesInformation and find a whether name is a substring, and output the income and arrivalTime
		foreach(CampaignSuppliesInformation supplyInfo : m_campaignSuppliesInformation) {
			if (prefabPathSource.EndsWith(supplyInfo.m_sName)) {
				string formattedLines = string.Format("    \"suppliesIncome\": %1,", supplyInfo.m_iIncome) + "\n";
				formattedLines += string.Format("    \"suppliesArrivalTime\": %1", supplyInfo.m_iArrivalTime);
				return formattedLines;
			}
		}

		return "";
	}

	
	string MakeObjectJSON(IEntity entity)
	{
		string outputString = MakeObjectJSONStart();
		
		outputString += MakeObjectJSONCommon(entity);
		
		if (m_componentSearchMode == EQComponentSearchMode.SUPPLY_CACHE) {
			outputString += ",\n" + MakeObjectJSONSupplyCache(entity);
		} else if (m_componentSearchMode == EQComponentSearchMode.CAMPAIGN_SUPPLIES) {
			outputString += ",\n" + MakeObjectJSONCampaignSupplies(entity);
		} else if (m_componentSearchMode == EQComponentSearchMode.VEHICLE) {
			// We cannot find vehicle spawn info because it's protected :(
		}
		
		outputString += MakeObjectJSONEnd();
		
		return outputString;
	}
	
	string CollectAllObjectJSON()
	{
		array<string> entitiesJSON = {};
		foreach(IEntity entity : m_entityResults) {
			entitiesJSON.Insert(MakeObjectJSON(entity));
		}
	
		return "[\n" + SCR_StringHelper.Join(",\n", entitiesJSON) + "\n]";
	}
	
	string GetCurrentSearchModeName()
	{
		typename t = EQComponentSearchMode;
		return t.GetVariableName(m_componentSearchMode);
	}
	
	string GetFilenameForMode()
	{
		string modeLower = GetCurrentSearchModeName();
		modeLower.ToLower();
		return m_outputFilePrefix + "_" + modeLower + ".json";
	}
	
	// Fixed data
	
	void PopulateCampaignSuppliesInformation()
	{
		if (m_campaignSuppliesInformation.IsEmpty())
		{
			m_campaignSuppliesInformation.Insert(new CampaignSuppliesInformation("T1Harbor.et", 3000, 900));
			m_campaignSuppliesInformation.Insert(new CampaignSuppliesInformation("T2Harbor.et", 2000, 900));
			m_campaignSuppliesInformation.Insert(new CampaignSuppliesInformation("T3Harbor.et", 1000, 600));
			m_campaignSuppliesInformation.Insert(new CampaignSuppliesInformation("Airfield.et", 2000, 600));
		}
	}
}
