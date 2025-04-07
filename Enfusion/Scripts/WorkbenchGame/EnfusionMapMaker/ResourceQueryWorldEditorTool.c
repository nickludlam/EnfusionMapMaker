enum EQComponentSearchMode {
	SUPPLIES,
	VEHICLES,
	VEHICLEREPAIR,
	REFUEL,
	POTENTIAL_MOB,
	CAPTURE_POINT,
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
	
	[Attribute(
		category: "Query",
		desc: "Merge radius",
		uiwidget: UIWidgets.Auto,
		defvalue: "1"
	)]
	float m_mergeRadius = 1.0;


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
		} else if (m_componentSearchMode == EQComponentSearchMode.VEHICLEREPAIR) {
			return filterVehicleRepairEntitiesCallback(e);
		} else if (m_componentSearchMode == EQComponentSearchMode.REFUEL) {
			return filterRefuelEntitiesCallback(e);
		} else if (m_componentSearchMode == EQComponentSearchMode.POTENTIAL_MOB) {
			return filterMOBEntitiesCallback(e);
		} else if (m_componentSearchMode == EQComponentSearchMode.CAPTURE_POINT) {
			return filterCapturePointEntitiesCallback(e);
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
	
	
	bool filterMOBEntitiesCallback(IEntity e) {
		if (e.FindComponent(SCR_CampaignMilitaryBaseComponent)) {
			SCR_CampaignMilitaryBaseComponent base = SCR_CampaignMilitaryBaseComponent.Cast(e.FindComponent(SCR_CampaignMilitaryBaseComponent));
			if (base.CanBeHQ() && base.GetType() == SCR_ECampaignBaseType.BASE) {
				return true;
			}
		}
		
		return false;
	}
	
	bool filterCapturePointEntitiesCallback(IEntity e) {
		if (e.FindComponent(SCR_CampaignMilitaryBaseComponent)) {
			SCR_CampaignMilitaryBaseComponent base = SCR_CampaignMilitaryBaseComponent.Cast(e.FindComponent(SCR_CampaignMilitaryBaseComponent));
			if (!base.CanBeHQ() && base.GetType() == SCR_ECampaignBaseType.BASE) {
				return true;
			}
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
				textFileW.WriteLine("  {");
				// Name
				string name = foundEntity.GetName();
				string formattedNameLine = string.Format("    \"name\": \"%1\",", name);
				textFileW.WriteLine(formattedNameLine);
				
				// Standard location
				vector position = foundEntity.GetOrigin();
				string formattedLocationLine = string.Format("    \"locationXZ\": [%1, %2],", position[0], position[2]);
				textFileW.WriteLine(formattedLocationLine);

				// Height				
				float worldHeight = api.GetTerrainSurfaceY(position[0], position[2]);
				float relativeHeight = position[1] - worldHeight;

				string formattedHeightLine = string.Format("    \"height\": %1,", relativeHeight);
				textFileW.WriteLine(formattedHeightLine);
				
				if (m_componentSearchMode == EQComponentSearchMode.SUPPLIES) {
					WriteSupplyCacheData(foundEntity, textFileW);
				}
				
				textFileW.Write("  },");
			}
			textFileW.WriteLine("]");
			textFileW.Close();
			
			int entityCount = m_entityResults.Count();
			PrintFormat("Wrote %1 coordinates to %2", entityCount, filepath);
		} else {
			PrintFormat("Failed to open file %1", filepath);
		}
	}
	
	void WriteSupplyCacheData(IEntity e, FileHandle fh) {
		// Resource values
		bool entityResourcesInfinite;
		float entityTotalResources;
		GetResourceAttributes(e, entityResourcesInfinite, entityTotalResources);
		
		float resourcesAvailable = entityTotalResources;
		if (entityResourcesInfinite) { resourcesAvailable = -1; }
		string formattedResourcesAvailableLine = string.Format("    \"resourcesAvailable\": %1", resourcesAvailable);
		fh.WriteLine(formattedResourcesAvailableLine);
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

								
				bool entityResourcesInfinite;
				float entityTotalResources;
				GetResourceAttributes(foundEntity, entityResourcesInfinite, entityTotalResources);

				
				Print("-------");
				Print(foundEntity);
				PrintFormat("  HEIGHT: %1", relativeHeight);
				if (entityResourcesInfinite) {
					PrintFormat("  RESOURCES: INFINITE");
				} else {
					PrintFormat("  RESOURCES: %1", entityTotalResources);
				}
			} else {
				Print(foundEntity);
			}
		}
		
		int entityCount = m_entityResults.Count();
		PrintFormat("Total entity count: %1", entityCount);
	}
	
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
}
