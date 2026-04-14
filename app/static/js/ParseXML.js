const validSleepStages = new Set([
    "HKCategoryValueSleepAnalysisAwake",
    "HKCategoryValueSleepAnalysisAsleepREM",
    "HKCategoryValueSleepAnalysisAsleepCore",
    "HKCategoryValueSleepAnalysisAsleepDeep"
]);

async function parseSleepXML(file) {

    const xml = await file.text()

    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(xml, "text/xml");

    if (xmlDoc.getElementsByTagName("parsererror").length > 0) {
        throw new Error("Invalid XML content.");
    }

    const records = xmlDoc.getElementsByTagName("Record");
    const sleepData = [];

    for (const record of records) {
        const type = record.getAttribute("type");
        const value = record.getAttribute("value");

        if (
            type === "HKCategoryTypeIdentifierSleepAnalysis" &&
            validSleepStages.has(value)
        ) {
            sleepData.push({
                stage: value,
                creation_date: record.getAttribute("creationDate"),
                start_date: record.getAttribute("startDate"),
                end_date: record.getAttribute("endDate"),
                source_name: record.getAttribute("sourceName")
            });
        }
    }

    return sleepData;
}

window.parseSleepXML = parseSleepXML;

