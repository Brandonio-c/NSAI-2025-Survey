// Helper to create list items
function createPaperListItem(article, showGithubLink = false, showDoiLink = false) {
  const li = document.createElement('li');
  const title = article.title || '(Untitled)';
  const author = article.author || '';
  const year = article.year || 'n.d.';
  
  // Get DOI/URL link
  let doiUrl = null;
  if (showDoiLink) {
    // First check excel_data for DOI/URL
    const excel = article.excel_data || {};
    doiUrl = excel['Paper DOI / URL'] || excel['DOI'] || excel['URL'] || excel['Paper DOI'] || excel['DOI / URL'] || '';
    
    // Fallback to article.url if not in excel_data
    if (!doiUrl || doiUrl === 'N/A' || doiUrl === '') {
      doiUrl = article.url || null;
    }
    
    // Clean up the URL
    if (doiUrl && doiUrl !== 'N/A' && doiUrl !== '' && doiUrl !== 'null') {
      doiUrl = doiUrl.toString().trim();
    } else {
      doiUrl = null;
    }
  }
  
  // Title link - use DOI/URL if available, otherwise just plain text
  const titleLink = doiUrl ? `<a href="${doiUrl}" target="_blank" rel="noopener">${title}</a>` : title;
  
  // Get GitHub link from repository_url field or excel_data if available
  let githubLink = '';
  if (showGithubLink) {
    // First check repository_url field (set by generate_final_lists.py)
    let repoUrl = article.repository_url || null;
    
    // Fallback to excel_data if repository_url not set
    if (!repoUrl) {
      const excel = article.excel_data || {};
      repoUrl = excel['Repository URL'] || excel['Repository URL '] || excel['GitHub URL'] || excel['Code URL'] || '';
    }
    
    if (repoUrl && repoUrl !== 'N/A' && repoUrl !== '' && repoUrl !== 'null') {
      githubLink = `<br><small class="text-muted"><strong>GitHub:</strong> <a href="${repoUrl}" target="_blank" rel="noopener">${repoUrl}</a></small>`;
    } else {
      githubLink = `<br><small class="text-muted"><strong>GitHub:</strong> No Codebase Provided</small>`;
    }
  }
  
  // Build DOI/URL link display
  let doiLink = '';
  if (showDoiLink && doiUrl) {
    doiLink = `<br><small class="text-muted"><strong>DOI/URL:</strong> <a href="${doiUrl}" target="_blank" rel="noopener">${doiUrl}</a></small>`;
  }
  
  li.innerHTML = `
    <div>
      <strong>${titleLink}</strong>
      <br>
      <small class="text-muted">
        ${author ? `Authors: ${author} • ` : ''}Year: ${year}
        ${article.article_id ? `• ID: ${article.article_id}` : ''}
      </small>
      ${doiLink}
      ${githubLink}
    </div>
  `;
  return li;
}

async function loadJSON(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Failed to load ${path}`);
  return response.json();
}

async function enrichPapersWithClusterLinks(papers, clusterLinksData) {
  /**Enrich papers with DOI/URL and GitHub links from cluster_papers_with_links.xlsx data.*/
  if (!clusterLinksData || !papers) return papers;
  
  return papers.map(paper => {
    const enriched = {...paper};
    const paperId = paper.article_id || '';
    
    // Extract Rayyan ID (e.g., "rayyan-242083763" -> "242083763")
    let rayyanId = null;
    if (paperId.toLowerCase().startsWith('rayyan-')) {
      rayyanId = paperId.substring(7).trim();
    } else if (paperId) {
      rayyanId = paperId.toString().trim();
    }
    
    if (!rayyanId) return enriched;
    
    // Search through all sheets in clusterLinksData
    for (const sheetName in clusterLinksData) {
      const sheet = clusterLinksData[sheetName];
      if (!Array.isArray(sheet)) continue;
      
      for (const row of sheet) {
        // Find Rayyan ID column - check paper_id first (most common)
        let rowRayyanId = null;
        
        // Try paper_id column first (most common in cluster file)
        if (row.paper_id) {
          const valStr = row.paper_id.toString().trim();
          rowRayyanId = valStr.toLowerCase().startsWith('rayyan-') 
            ? valStr.substring(7).trim() 
            : valStr.trim();
        } else {
          // Fallback to other ID patterns
          const idPatterns = [
            (k) => k.toLowerCase().includes('rayyan') && k.toLowerCase().includes('id'),
            (k) => k.toLowerCase().includes('paper') && k.toLowerCase().includes('id'),
            (k) => k.toLowerCase() === 'id',
            (k) => k.toLowerCase() === 'paper id'
          ];
          
          for (const key in row) {
            for (const pattern of idPatterns) {
              if (pattern(key)) {
                const val = row[key];
                if (val) {
                  const valStr = val.toString().trim();
                  rowRayyanId = valStr.toLowerCase().startsWith('rayyan-') 
                    ? valStr.substring(7).trim() 
                    : valStr.trim();
                  if (rowRayyanId) break;
                }
              }
            }
            if (rowRayyanId) break;
          }
        }
        
        // Match by Rayyan ID (normalize both for comparison)
        const normalizedRayyanId = rayyanId.toString().trim();
        const normalizedRowId = rowRayyanId ? rowRayyanId.toString().trim() : null;
        
        if (normalizedRowId && normalizedRowId === normalizedRayyanId) {
          // Found match! Extract DOI/URL and GitHub links
          
          // Find DOI/URL - check other_links first (common in cluster file)
          if (!enriched.url && !enriched.excel_data?.['Paper DOI / URL']) {
            // Check other_links column (contains DOI/paper URLs, sometimes GitHub URLs too)
            if (row.other_links && row.other_links !== 'N/A') {
              const linksStr = row.other_links.toString().trim();
              if (linksStr && !linksStr.match(/^(N\/A|None|null|nan)$/i) && linksStr.length > 3) {
                // other_links might contain multiple URLs separated by commas or newlines
                const links = linksStr.split(/[,\n]/).map(l => l.trim()).filter(l => l && l !== 'N/A');
                for (const link of links) {
                  // Skip GitHub/GitLab URLs (they'll be handled as repository URLs)
                  if (link.includes('github.com') || link.includes('gitlab') || link.includes('bitbucket')) {
                    continue;
                  }
                  
                  // Check if it's a paper URL/DOI
                  if (link.startsWith('http') && 
                      (link.includes('doi.org') || link.includes('arxiv.org') || 
                       link.includes('acm.org') || link.includes('ieee.org') ||
                       link.includes('semanticscholar.org') || link.includes('openreview.net') ||
                       link.includes('researchgate.net') || link.includes('ceur-ws.org') ||
                       link.includes('.pdf') || link.includes('pubmed') ||
                       (!link.includes('github') && !link.includes('gitlab') && link.includes('.')))) {
                    if (!enriched.excel_data) enriched.excel_data = {};
                    enriched.excel_data['Paper DOI / URL'] = link;
                    enriched.url = link;
                    break;
                  }
                }
              }
            }
            
            // Fallback to other URL patterns
            if (!enriched.url) {
              const doiUrlPatterns = [
                (k) => k.toLowerCase().includes('doi') && k.toLowerCase().includes('url'),
                (k) => k.toLowerCase().includes('doi'),
                (k) => k.toLowerCase().includes('url') && !k.toLowerCase().includes('repository') && !k.toLowerCase().includes('github'),
                (k) => k.toLowerCase().includes('link') && !k.toLowerCase().includes('repository')
              ];
              
              for (const pattern of doiUrlPatterns) {
                for (const key in row) {
                  if (pattern(key)) {
                    const val = row[key];
                    if (val) {
                      const valStr = val.toString().trim();
                      if (valStr && !valStr.match(/^(N\/A|None|null|nan)$/i) && valStr.length > 3) {
                        if (!enriched.excel_data) enriched.excel_data = {};
                        enriched.excel_data['Paper DOI / URL'] = valStr;
                        enriched.url = valStr;
                        break;
                      }
                    }
                  }
                }
                if (enriched.url) break;
              }
            }
          }
          
          // Find GitHub/Repository URL - check codebase column first (most common)
          if (!enriched.repository_url && !enriched.excel_data?.['Repository URL']) {
            // Check codebase column (contains GitHub URLs in cluster file)
            if (row.codebase && row.codebase !== 'N/A') {
              const codebaseStr = row.codebase.toString().trim();
              if (codebaseStr && !codebaseStr.match(/^(N\/A|None|null|nan)$/i)) {
                // Check if it's a URL
                if (codebaseStr.startsWith('http') || codebaseStr.includes('github') || 
                    codebaseStr.includes('gitlab') || codebaseStr.includes('bitbucket')) {
                  if (!enriched.excel_data) enriched.excel_data = {};
                  enriched.excel_data['Repository URL'] = codebaseStr;
                  enriched.repository_url = codebaseStr;
                }
              }
            }
            
            // Also check other_links for GitHub URLs (fallback - sometimes GitHub URL is in other_links)
            if (!enriched.repository_url && row.other_links && row.other_links !== 'N/A') {
              const linksStr = row.other_links.toString().trim();
              if (linksStr && !linksStr.match(/^(N\/A|None|null|nan)$/i)) {
                const links = linksStr.split(/[,\n]/).map(l => l.trim()).filter(l => l && l !== 'N/A');
                for (const link of links) {
                  // Check if it's a GitHub/GitLab/Bitbucket URL
                  if (link.includes('github.com') || link.includes('gitlab.com') || 
                      link.includes('bitbucket.org') || link.includes('gitlab')) {
                    if (!enriched.excel_data) enriched.excel_data = {};
                    enriched.excel_data['Repository URL'] = link;
                    enriched.repository_url = link;
                    break;
                  }
                }
              }
            }
            
            // Fallback to other repository patterns
            if (!enriched.repository_url) {
              const repoPatterns = [
                (k) => k.toLowerCase().includes('github'),
                (k) => k.toLowerCase().includes('repository'),
                (k) => k.toLowerCase().includes('repo') && !k.toLowerCase().includes('doi'),
                (k) => k.toLowerCase().includes('code') && k.toLowerCase().includes('url'),
                (k) => k.toLowerCase().includes('gitlab')
              ];
              
              for (const pattern of repoPatterns) {
                for (const key in row) {
                  if (pattern(key)) {
                    const val = row[key];
                    if (val) {
                      const urlStr = val.toString().trim();
                      if (urlStr && !urlStr.match(/^(N\/A|None|null|nan)$/i)) {
                        if (urlStr.startsWith('http') || urlStr.includes('github') || 
                            urlStr.includes('gitlab') || urlStr.includes('bitbucket') ||
                            (urlStr.includes('.') && urlStr.length > 5)) {
                          if (!enriched.excel_data) enriched.excel_data = {};
                          enriched.excel_data['Repository URL'] = urlStr;
                          enriched.repository_url = urlStr;
                          break;
                        }
                      }
                    }
                  }
                }
                if (enriched.repository_url) break;
              }
            }
          }
          
          // Found match, no need to continue searching
          break;
        }
      }
    }
    
    return enriched;
  });
}

async function init() {
  try {
    const [criteriaData, overviewData, includeData, excludeData, finalIncludeData, finalExcludeData, clusterLinksData] = await Promise.all([
      loadJSON('data/inclusion_exclusion_criteria.json'),
      loadJSON('data/screening_overview_enriched.json'),
      loadJSON('data/include.json'),
      loadJSON('data/exclude.json'),
      loadJSON('data/final_include.json'),
      loadJSON('data/final_exclude.json'),
      loadJSON('data/cluster_papers_with_links.json').catch(() => null) // Optional file
    ]);

    // Enrich in-scope papers with cluster links data if available
    const enrichedIncludeData = clusterLinksData 
      ? await enrichPapersWithClusterLinks(includeData, clusterLinksData)
      : includeData;
    
    // Enrich out-of-scope papers too
    const enrichedExcludeData = clusterLinksData
      ? await enrichPapersWithClusterLinks(excludeData, clusterLinksData)
      : excludeData;

    populateCriteria(criteriaData);
    populateOverview(overviewData);
    populatePaperLists(enrichedIncludeData, enrichedExcludeData, overviewData);
    populateFinalPaperLists(finalIncludeData, finalExcludeData);
  } catch (err) {
    console.error(err);
    alert('Error loading data. See console for details.');
  }
}

function populateCriteria(data) {
  const section = document.getElementById('criteriaSection');
  section.innerHTML = '';

  // Research question
  const rq = document.createElement('p');
  rq.innerHTML = `<strong>Research question:</strong> ${data.inclusion_criteria[0]['research_question']}`;
  section.appendChild(rq);

  // Objective statement (if available)
  if (data.inclusion_criteria[0]['objective-statement']) {
    const obj = document.createElement('p');
    obj.className = 'mt-3';
    obj.innerHTML = `<strong>Objective:</strong> ${data.inclusion_criteria[0]['objective-statement']}`;
    section.appendChild(obj);
  }

  // Inclusion criteria
  const incHeader = document.createElement('h5');
  incHeader.className = 'mt-4';
  incHeader.textContent = 'Inclusion Criteria';
  section.appendChild(incHeader);
  const incList = document.createElement('ul');
  
  data.inclusion_criteria.forEach(c => {
    const li = document.createElement('li');
    // For the first criterion, use a shorter description
    if (c.name === 'Neuro‑Symbolic Integration') {
      li.textContent = `${c.name}: Study proposes, evaluates, or applies a hybrid system that explicitly combines neural/connectionist components with symbolic reasoning or structured knowledge representations.`;
    } else {
      li.textContent = `${c.name}: ${c.description}`;
    }
    incList.appendChild(li);
  });
  section.appendChild(incList);

  // Exclusion criteria
  const excHeader = document.createElement('h5');
  excHeader.classList.add('mt-3');
  excHeader.textContent = 'Exclusion Criteria';
  section.appendChild(excHeader);
  const excList = document.createElement('ul');
  data.exclusion_criteria.forEach(c => {
    const li = document.createElement('li');
    li.textContent = `${c.name}`;
    excList.appendChild(li);
  });
  section.appendChild(excList);
}

function populateOverview(data) {
  const section = document.getElementById('overviewSection');
  section.innerHTML = '';

  const screening = data.rayyan_screening;
  const includedCount = 84; // Final included count after data extraction
  const excludedCount = 2283; // Final excluded count (1851 out-of-scope + 432 excluded from in-scope)

  const summary = document.createElement('p');
  summary.innerHTML = `<strong>Total included:</strong> ${includedCount} &nbsp;&nbsp;|&nbsp;&nbsp; <strong>Total excluded:</strong> ${excludedCount}`;
  section.appendChild(summary);

  // Add Sankey diagram
  const sankeyDiv = document.createElement('div');
  sankeyDiv.className = 'mt-4 mb-4';
  
  // Create header with export buttons
  const headerDiv = document.createElement('div');
  headerDiv.style.display = 'flex';
  headerDiv.style.justifyContent = 'space-between';
  headerDiv.style.alignItems = 'center';
  headerDiv.style.marginBottom = '10px';
  
  const title = document.createElement('h5');
  title.style.margin = '0';
  title.textContent = 'Screening Flow Diagram';
  headerDiv.appendChild(title);
  
  const buttonGroup = document.createElement('div');
  buttonGroup.style.display = 'flex';
  buttonGroup.style.gap = '10px';
  
  const exportPngBtn = document.createElement('button');
  exportPngBtn.className = 'btn btn-sm btn-outline-primary';
  exportPngBtn.textContent = 'Export PNG';
  exportPngBtn.onclick = () => exportSankeyAsPNG();
  
  const exportPdfBtn = document.createElement('button');
  exportPdfBtn.className = 'btn btn-sm btn-outline-danger';
  exportPdfBtn.textContent = 'Export PDF';
  exportPdfBtn.onclick = () => exportSankeyAsPDF();
  
  buttonGroup.appendChild(exportPngBtn);
  buttonGroup.appendChild(exportPdfBtn);
  headerDiv.appendChild(buttonGroup);
  
  sankeyDiv.appendChild(headerDiv);
  
  const sankeyContainer = document.createElement('div');
  sankeyContainer.id = 'sankey-container';
  sankeyContainer.style.height = '400px';
  sankeyContainer.style.width = '100%';
  sankeyContainer.style.overflowX = 'auto'; // Allow horizontal scrolling if needed
  sankeyDiv.appendChild(sankeyContainer);
  section.appendChild(sankeyDiv);

  // Create Sankey diagram
  createSankeyDiagram(data);

  // Pie Chart 1: Title and Abstract Screening Exclusion Reasons
  const pieChart1Title = document.createElement('h5');
  pieChart1Title.className = 'mt-4 mb-3';
  pieChart1Title.textContent = 'Pie Chart 1: Title and Abstract Screening Exclusion Reasons';
  section.appendChild(pieChart1Title);

  const canvas1 = document.createElement('canvas');
  canvas1.id = 'exclusionPie';
  canvas1.height = 300;
  section.appendChild(canvas1);

  // Breakdown table
  const table = document.createElement('table');
  table.className = 'table table-sm table-striped mt-3';
  const thead = document.createElement('thead');
  thead.innerHTML = '<tr><th>Exclusion Reason</th><th>Count</th><th>%</th></tr>';
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  table.appendChild(tbody);

  const labels = [];
  const counts = [];

  const breakdown = screening.excluded_out_of_scope.breakdown.individual_criteria_counts;
  
  // Consolidate categories according to the mapping
  const consolidatedData = {};
  
  Object.entries(breakdown).forEach(([reason, info]) => {
    let consolidatedReason;
    
    // Map to consolidated categories
    if (reason === 'Survey/review paper' || reason === 'Review paper' || reason === 'Background article') {
      consolidatedReason = 'review/background article';
    } else if (reason === 'Other/Unclear' || reason === '__EXR__wrong outcome' || reason === '__EXR__engl' || reason === '__EXR__v') {
      consolidatedReason = 'No codebase/implementation';
    } else if (reason === '__EXR__no-fulltext') {
      consolidatedReason = 'no-fulltext';
    } else if (reason === '__EXR__not-in-english' || reason === '__EXR__foreign language') {
      consolidatedReason = 'not-in-english';
    } else {
      consolidatedReason = reason;
    }
    
    if (!consolidatedData[consolidatedReason]) {
      consolidatedData[consolidatedReason] = { count: 0, percentage: 0 };
    }
    consolidatedData[consolidatedReason].count += info.count;
    consolidatedData[consolidatedReason].percentage += info.percentage;
  });
  
  // Sort by count (descending)
  const sortedEntries = Object.entries(consolidatedData).sort((a, b) => b[1].count - a[1].count);
  
  sortedEntries.forEach(([reason, info]) => {
    labels.push(reason);
    counts.push(info.count);
    const row = document.createElement('tr');
    row.innerHTML = `<td>${reason}</td><td>${info.count}</td><td>${info.percentage.toFixed(1)}%</td>`;
    tbody.appendChild(row);
  });
  section.appendChild(table);

  // Render pie chart 1
  new Chart(canvas1, {
    type: 'pie',
    data: {
      labels,
      datasets: [{
        data: counts,
        backgroundColor: labels.map(() => `hsl(${Math.random()*360},70%,70%)`)
      }]
    },
    options: {
      plugins: {
        legend: { position: 'bottom' },
        title: {
          display: false // Title is handled by h5 element above
        }
      }
    }
  });

  // Pie Chart 2: In-Scope Papers Breakdown
  const pieChart2Title = document.createElement('h5');
  pieChart2Title.className = 'mt-5 mb-3';
  pieChart2Title.textContent = 'In-Scope Papers Breakdown: Included and Excluded Papers with Reasons';
  section.appendChild(pieChart2Title);

  const canvas2 = document.createElement('canvas');
  canvas2.id = 'reproductionPie';
  canvas2.height = 300;
  section.appendChild(canvas2);

  // Data from funnel breakdown (same as used in Sankey diagram)
  // Numbers match funnel_overall_pie.png/pdf
  // Note: "Partially Reproduced (below threshold)" removed as count is 0 (all such papers have "Include" in decision column)
  const funnelBreakdown = [
    { name: 'Fully Reproduced', count: 48 },
    { name: 'Partially Reproduced (above threshold)', count: 37 },
    { name: 'Has All Artifacts but Failed', count: 7 },
    { name: 'Missing Code', count: 42 },
    { name: 'Not Attempted - No Fulltext', count: 6 },
    { name: 'Not Attempted - Off Topic', count: 30 },
    { name: 'Not Attempted - Not a Research Article', count: 1 },
    { name: 'Not Attempted - Background Article', count: 3 },
    { name: 'No quantitative evaluation', count: 21 },
    { name: 'Missing Some Artifacts (not code, e.g. data, model, etc.)', count: 321 }
  ];

  const reproLabels = [];
  const reproCounts = [];
  const reproColors = [
    '#2ecc71', // Green for Fully Reproduced
    '#e74c3c', // Red for Partially (above threshold)
    '#8b4513', // Brown for Has All Artifacts but Failed
    '#e91e63', // Pink for Missing Code
    '#95a5a6', // Gray for Not Attempted - No Fulltext
    '#f39c12', // Yellow/Orange for Not Attempted - Off Topic
    '#3498db', // Blue for Not Attempted - Not a Research Article
    '#34495e', // Dark Blue for Not Attempted - Background Article
    '#9370DB', // Purple for No quantitative evaluation
    '#e67e22'  // Orange for Missing Some Artifacts
  ];

  funnelBreakdown.forEach((item, idx) => {
    reproLabels.push(`${item.name} (${item.count})`);
    reproCounts.push(item.count);
  });

  // Render pie chart 2
  new Chart(canvas2, {
    type: 'pie',
    data: {
      labels: reproLabels,
      datasets: [{
        data: reproCounts,
        backgroundColor: reproColors
      }]
    },
    options: {
      plugins: {
        legend: { position: 'bottom' },
        title: {
          display: false // Title is handled by h5 element above
        }
      }
    }
  });

  // Breakdown table for Pie Chart 2
  const table2 = document.createElement('table');
  table2.className = 'table table-sm table-striped mt-3';
  const thead2 = document.createElement('thead');
  thead2.innerHTML = '<tr><th>Reproduction Status / Exclusion Reason</th><th>Count</th><th>%</th></tr>';
  table2.appendChild(thead2);
  const tbody2 = document.createElement('tbody');
  table2.appendChild(tbody2);

  const totalPapers = 516; // Total papers in-scope
  funnelBreakdown.forEach((item) => {
    const percentage = (item.count / totalPapers * 100).toFixed(1);
    const row = document.createElement('tr');
    row.innerHTML = `<td>${item.name}</td><td>${item.count}</td><td>${percentage}%</td>`;
    tbody2.appendChild(row);
  });
  section.appendChild(table2);
}

function createSankeyDiagram(data) {
  const searchData = data.search_and_deduplication;
  const screening = data.rayyan_screening;
  
  const totalHits = searchData.total_results_retrieved;
  const afterDedup = searchData.after_dedup_rayyan;
  const included = screening.included_within_scope;
  const excluded = screening.excluded_out_of_scope.total_count || screening.excluded_out_of_scope;
  const duplicatesRemoved = totalHits - afterDedup;

  // Get exclusion breakdown and consolidate categories using the exact same logic as the exclusion reason table
  const exclusionBreakdown = screening.excluded_out_of_scope.breakdown.individual_criteria_counts;
  
  // Consolidate categories for Sankey diagram (same logic as exclusion reason table)
  const consolidatedBreakdown = {};
  Object.entries(exclusionBreakdown).forEach(([reason, info]) => {
    let consolidatedReason;
    
    if (reason === 'Survey/review paper' || reason === 'Review paper' || reason === 'Background article') {
      consolidatedReason = 'review/background article';
    } else if (reason === 'Other/Unclear' || reason === '__EXR__wrong outcome' || reason === '__EXR__engl' || reason === '__EXR__v') {
      consolidatedReason = 'No codebase/implementation';
    } else if (reason === '__EXR__no-fulltext') {
      consolidatedReason = 'no-fulltext';
    } else if (reason === '__EXR__not-in-english' || reason === '__EXR__foreign language') {
      consolidatedReason = 'not-in-english';
    } else {
      consolidatedReason = reason;
    }
    
    if (!consolidatedBreakdown[consolidatedReason]) {
      consolidatedBreakdown[consolidatedReason] = { count: 0, percentage: 0 };
    }
    consolidatedBreakdown[consolidatedReason].count += info.count;
    consolidatedBreakdown[consolidatedReason].percentage += info.percentage;
  });
  
  // Sort by count (descending) - same as exclusion reason table
  const sortedEntries = Object.entries(consolidatedBreakdown).sort((a, b) => b[1].count - a[1].count);
  const topExclusionReasons = sortedEntries.slice(0, 8); // Top 8 reasons to include no-fulltext, duplicate, not-in-english

  // Create Sankey data with proper flow
  const nodes = [
    { id: 0, name: `Total Hits (${totalHits.toLocaleString()})` },
    { id: 1, name: `Duplicates Removed (${duplicatesRemoved.toLocaleString()})` },
    { id: 2, name: `After Dedup (${afterDedup.toLocaleString()})` },
    { id: 3, name: `In-Scope (${included})` }
  ];

  const links = [
    { source: 0, target: 1, value: duplicatesRemoved },
    { source: 0, target: 2, value: afterDedup },
    { source: 2, target: 3, value: included }
  ];

  // Add top exclusion reasons as separate nodes
  let nodeId = 4;
  topExclusionReasons.forEach(([reason, info]) => {
    nodes.push({ id: nodeId, name: `${reason} (${info.count})` });
    links.push({ source: 2, target: nodeId, value: info.count });
    nodeId++;
  });

  // Add remaining excluded papers as "Other reasons"
  const accountedFor = topExclusionReasons.reduce((sum, [_, info]) => sum + info.count, 0);
  const remainingExcluded = excluded - accountedFor;
  if (remainingExcluded > 0) {
    nodes.push({ id: nodeId, name: `Other reasons (${remainingExcluded})` });
    links.push({ source: 2, target: nodeId, value: remainingExcluded });
    nodeId++;
  }

  // Add funnel breakdown nodes - DATA EXTRACTION STAGE
  // All flowing from In-Scope (node 3) - these represent data extraction results
  // Data from funnel_overall_pie.png - updated to match actual pie chart
  // Note: "Partially Reproduced (below threshold)" removed as count is 0 (all such papers have "Include" in decision column)
  const funnelBreakdown = [
    { name: 'Fully Reproduced', count: 48 },
    { name: 'Partially Reproduced (above threshold)', count: 37 },
    { name: 'Has All Artifacts but Failed', count: 7 },
    { name: 'Missing Code', count: 42 },
    { name: 'Not Attempted - No Fulltext', count: 6 },
    { name: 'Not Attempted - Off Topic', count: 30 },
    { name: 'Not Attempted - Not a Research Article', count: 1 },
    { name: 'Not Attempted - Background Article', count: 3 },
    { name: 'No quantitative evaluation', count: 21 },
    { name: 'Missing Some Artifacts (not code, e.g. data, model, etc.)', count: 321 }
  ];

  const funnelStartNodeId = nodeId; // Store starting ID for funnel nodes
  funnelBreakdown.forEach((item) => {
    nodes.push({ id: nodeId, name: `${item.name} (${item.count})` });
    links.push({ source: 3, target: nodeId, value: item.count }); // All from In-Scope (node 3)
    nodeId++;
  });

  // Create the final Sankey data object
  const sankeyData = { nodes, links };

  // Set up the SVG - wider to accommodate funnel nodes
  const container = document.getElementById('sankey-container');
  // Use a fixed wide width to ensure funnel nodes are visible
  let width = 2000; // Fixed wide width
  const height = 400;
  const margin = { top: 20, right: 20, bottom: 20, left: 20 };

  // Clear any existing SVG
  d3.select('#sankey-container').selectAll('*').remove();

  let svg = d3.select('#sankey-container')
    .append('svg')
    .attr('width', width)
    .attr('height', height);
  
  const svgGroup = svg.append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`);

  // Color scale
  const color = d3.scaleOrdinal(d3.schemeCategory10);

  // Create the Sankey layout - FIRST run without funnel nodes to get original positions
  // Use narrower extent to compress the original diagram
  const originalDiagramWidth = 600; // Reduced width for original diagram
  const sankey = d3.sankey()
    .nodeWidth(12) // Slightly narrower nodes
    .nodePadding(8) // Less padding
    .extent([[1, 1], [originalDiagramWidth - 1, height - margin.top - margin.bottom - 5]]);

  // Create data WITHOUT funnel nodes to get original layout
  const nodesWithoutFunnel = sankeyData.nodes.filter(n => n.id < funnelStartNodeId);
  const linksWithoutFunnel = sankeyData.links.filter(l => l.target < funnelStartNodeId);
  
  // Apply layout to original nodes only
  const { nodes: originalNodes, links: originalLinks } = sankey({
    nodes: nodesWithoutFunnel.map(d => Object.assign({}, d)),
    links: linksWithoutFunnel.map(d => Object.assign({}, d))
  });

  // Move exclusion nodes (nodes with id >= 4) AND In-Scope node (id 3) further to the right
  // to extend the orange links from "After Dedup" (node 2) and align them all
  const exclusionNodeStartId = 3; // Start from In-Scope (id 3) to include it
  const exclusionExtension = 225; // Reduced by 1/4: 300 * 0.75 = 225px
  
  originalNodes.forEach(node => {
    // If this is In-Scope (id 3) or an exclusion node (id >= 4 and < funnelStartNodeId)
    if (node.id >= exclusionNodeStartId && node.id < funnelStartNodeId) {
      node.x0 += exclusionExtension;
      node.x1 += exclusionExtension;
    }
  });

  // Now add funnel nodes positioned to the right
  const funnelNodeIds = [];
  for (let i = funnelStartNodeId; i < funnelStartNodeId + funnelBreakdown.length; i++) {
    funnelNodeIds.push(i);
  }
  
  // Find the rightmost x position of original nodes
  const rightmostX = Math.max(...originalNodes.map(n => n.x1), 0);
  
  // Position funnel nodes in a new column to the right (moved MUCH further right to extend link length)
  const funnelColumnX = originalDiagramWidth + 400; // 400px gap to show separation and extend link length
  const availableHeight = height - margin.top - margin.bottom;
  const nodeSpacing = availableHeight / (funnelBreakdown.length + 1);
  
  const funnelNodes = [];
  funnelNodeIds.forEach((funnelId, idx) => {
    const originalNode = sankeyData.nodes.find(n => n.id === funnelId);
    const nodeHeight = Math.max(8, nodeSpacing * 0.85);
    const yPos = margin.top + (idx + 1) * nodeSpacing - (nodeHeight / 2);
    
    funnelNodes.push({
      id: funnelId,
      name: originalNode.name,
      x0: funnelColumnX,
      x1: funnelColumnX + 15,
      y0: yPos,
      y1: yPos + nodeHeight
    });
  });
  
  // Combine original nodes with funnel nodes
  const layoutNodes = [...originalNodes, ...funnelNodes];
  
  // Create links for funnel nodes
  const funnelLinks = [];
  const inScopeNode = originalNodes.find(n => n.id === 3);
  funnelNodeIds.forEach((funnelId, idx) => {
    const funnelNode = funnelNodes[idx];
    const linkValue = funnelBreakdown[idx].count;
    
    // Calculate link path with extended length for large links (like Missing Some Artifacts)
    const linkMidpointX = inScopeNode.x1 + (funnelColumnX - inScopeNode.x1) * 0.6; // Extend link path
    
    funnelLinks.push({
      source: inScopeNode,
      target: funnelNode,
      value: linkValue,
      y0: inScopeNode.y0 + (inScopeNode.y1 - inScopeNode.y0) / 2,
      y1: funnelNode.y0 + (funnelNode.y1 - funnelNode.y0) / 2,
      width: Math.max(1, Math.min(linkValue * 0.15, 15)), // Much smaller width, capped at 15px max
      // Store extended path info for custom rendering if needed
      extendedPath: linkValue > 200 // For large links like Missing Some Artifacts (311)
    });
  });
  
  // Combine original links with funnel links
  const layoutLinks = [...originalLinks, ...funnelLinks];
  
  // Update SVG width to ensure funnel nodes are visible (increased for more spacing)
  const finalRequiredWidth = funnelColumnX + 15 + margin.left + margin.right + 450; // Extra space for labels (increased to 450)
  if (finalRequiredWidth > width) {
    width = finalRequiredWidth;
    svg.attr('width', width);
  }

  // Add the links - render BEFORE nodes so labels appear on top
  const linkGroup = svgGroup.append('g')
    .selectAll('path')
    .data(layoutLinks)
    .join('path')
    .attr('class', 'link')
    .attr('d', d3.sankeyLinkHorizontal())
    .attr('fill', 'none') // CRITICAL: Set fill to none to prevent black fill on export
    .attr('stroke', d => color(d.source.id))
    .attr('stroke-width', d => Math.max(1, d.width))
    .attr('stroke-opacity', 0.4) // Set as attribute, not just style
    .style('stroke-opacity', 0.4) // Also set as style for browser display
    .style('z-index', 1) // Behind nodes
    .on('mouseover', function(event, d) {
      d3.select(this).style('stroke-opacity', 0.7);
    })
    .on('mouseout', function(event, d) {
      d3.select(this).style('stroke-opacity', 0.4);
    });

  // Add the nodes - render AFTER links so they appear on top
  const node = svgGroup.append('g')
    .selectAll('g')
    .data(layoutNodes)
    .join('g')
    .attr('class', 'node')
    .style('z-index', 2); // Above links

  node.append('rect')
    .attr('x', d => d.x0)
    .attr('y', d => d.y0)
    .attr('height', d => d.y1 - d.y0)
    .attr('width', d => d.x1 - d.x0)
    .attr('fill', d => color(d.id))
    .attr('stroke', '#000');

  // Add the node labels - render AFTER everything so they're on top
  // Create a set for faster lookup
  const funnelNodeIdSet = new Set(funnelNodeIds);
  
  node.append('text')
    .attr('x', d => {
      // For funnel nodes (rightmost), place labels further to the right to avoid link overlap
      if (funnelNodeIdSet.has(d.id)) {
        return d.x1 + 18; // Further increased spacing to avoid link overlap (was 15)
      }
      // For original nodes, use original logic
      return d.x0 < (originalDiagramWidth) / 2 ? d.x1 + 6 : d.x0 - 6;
    })
    .attr('y', d => (d.y1 + d.y0) / 2)
    .attr('dy', '0.35em')
    .attr('text-anchor', d => {
      // For funnel nodes, always anchor to start (left side of text, so it appears to the right)
      if (funnelNodeIdSet.has(d.id)) {
        return 'start';
      }
      // For original nodes, use original logic
      return d.x0 < (originalDiagramWidth) / 2 ? 'start' : 'end';
    })
    .style('font-size', '10px') // Smaller font to reduce overlap
    .style('pointer-events', 'none') // Allow clicks to pass through
    .style('fill', '#000') // Ensure text is visible
    .style('font-weight', 'normal') // Not bold to reduce visual weight
    .text(d => d.name);

  // Add value labels on the links
  svgGroup.append('g')
    .selectAll('text')
    .data(layoutLinks)
    .join('text')
    .attr('x', d => (d.source.x1 + d.target.x0) / 2)
    .attr('y', d => (d.y0 + d.y1) / 2)
    .attr('dy', '0.35em')
    .attr('text-anchor', 'middle')
    .style('font-size', '12px')
    .style('font-weight', 'bold')
    .text(d => d.value.toLocaleString());
}

// Export functions for Sankey diagram
function exportSankeyAsPNG() {
  const container = document.getElementById('sankey-container');
  const svg = container.querySelector('svg');
  
  if (!svg) {
    alert('Sankey diagram not found. Please wait for it to load.');
    return;
  }
  
  // Clone the SVG to avoid modifying the original
  const svgClone = svg.cloneNode(true);
  
  // Function to inline computed styles - critical for proper export
  function inlineStyles(element) {
    const computed = window.getComputedStyle(element);
    const styleProps = [
      'fill', 'stroke', 'stroke-width', 'stroke-opacity', 'opacity',
      'font-family', 'font-size', 'font-weight', 'text-anchor'
    ];
    
    styleProps.forEach(prop => {
      const value = computed.getPropertyValue(prop);
      if (value && value !== 'none' && value !== 'rgba(0, 0, 0, 0)') {
        const attrName = prop.replace(/-([a-z])/g, (g) => g[1].toUpperCase());
        element.setAttribute(attrName, value);
      }
    });
  }
  
  // Inline styles for all elements - this preserves styles during export
  const allElements = svgClone.querySelectorAll('*');
  allElements.forEach(el => {
    inlineStyles(el);
  });
  
  // Remove black strokes from nodes
  const nodeRects = svgClone.querySelectorAll('.node rect');
  nodeRects.forEach(rect => {
    const computed = window.getComputedStyle(rect);
    const stroke = computed.stroke;
    if (stroke === 'rgb(0, 0, 0)' || stroke === '#000' || stroke === 'black') {
      rect.setAttribute('stroke', 'none');
    }
  });
  
  // CRITICAL FIX: Set fill='none' on all links - SVG paths default to black fill!
  const links = svgClone.querySelectorAll('.link');
  links.forEach(link => {
    // THIS IS THE KEY FIX - SVG paths default to black fill if not set
    link.setAttribute('fill', 'none');
    
    const computed = window.getComputedStyle(link);
    const stroke = computed.stroke;
    const originalStroke = link.getAttribute('stroke');
    
    // Preserve the original colored stroke
    if (originalStroke && originalStroke !== '#000' && originalStroke !== 'black' && originalStroke !== 'rgb(0, 0, 0)') {
      link.setAttribute('stroke', originalStroke);
    } else if (stroke && stroke !== 'rgb(0, 0, 0)' && stroke !== '#000' && stroke !== 'black') {
      link.setAttribute('stroke', stroke);
    }
    
    // Ensure stroke-opacity is set
    const strokeOpacity = link.getAttribute('stroke-opacity') || computed.getPropertyValue('stroke-opacity') || '0.4';
    link.setAttribute('stroke-opacity', strokeOpacity);
    
    link.removeAttribute('filter');
  });
  
  // Remove shadow filters
  const defs = svgClone.querySelectorAll('defs');
  defs.forEach(def => {
    const filters = def.querySelectorAll('filter');
    filters.forEach(filter => {
      const filterId = filter.getAttribute('id');
      if (filterId && (filterId.includes('shadow') || filterId.includes('drop'))) {
        filter.remove();
      }
    });
  });
  
  // Get actual SVG dimensions
  const width = svg.width.baseVal.value || svg.getBoundingClientRect().width;
  const height = svg.height.baseVal.value || svg.getBoundingClientRect().height;
  
  // Ensure the clone has explicit dimensions
  svgClone.setAttribute('width', width);
  svgClone.setAttribute('height', height);
  svgClone.setAttribute('style', 'background: white;');
  
  // Serialize the cloned SVG with proper namespace
  const svgData = new XMLSerializer().serializeToString(svgClone);
  
  // Add XML declaration and ensure proper namespace
  const svgWithNamespace = '<?xml version="1.0" encoding="UTF-8"?>' +
    '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" ' +
    `width="${width}" height="${height}">` +
    '<rect width="100%" height="100%" fill="white"/>' +
    svgData.replace(/<svg[^>]*>/, '').replace('</svg>', '') +
    '</svg>';
  
  // Create canvas
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  
  // Set white background
  ctx.fillStyle = 'white';
  ctx.fillRect(0, 0, width, height);
  
  // Convert SVG to image
  const svgBlob = new Blob([svgWithNamespace], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(svgBlob);
  
  const img = new Image();
  img.onload = function() {
    ctx.drawImage(img, 0, 0, width, height);
    URL.revokeObjectURL(url);
    
    // Download as PNG
    canvas.toBlob(function(blob) {
      const link = document.createElement('a');
      link.download = 'sankey_diagram.png';
      link.href = URL.createObjectURL(blob);
      link.click();
      URL.revokeObjectURL(link.href);
    }, 'image/png');
  };
  img.onerror = function() {
    alert('Error exporting PNG. Please try again.');
    URL.revokeObjectURL(url);
  };
  img.src = url;
}

function exportSankeyAsPDF() {
  const container = document.getElementById('sankey-container');
  const svg = container.querySelector('svg');
  
  if (!svg) {
    alert('Sankey diagram not found. Please wait for it to load.');
    return;
  }
  
  // Check if jsPDF is loaded
  if (typeof window.jspdf === 'undefined') {
    // Load jsPDF dynamically
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js';
    script.onload = () => {
      exportSankeyAsPDF(); // Retry after loading
    };
    document.head.appendChild(script);
    return;
  }
  
  // Clone the SVG to avoid modifying the original
  const svgClone = svg.cloneNode(true);
  
  // Function to inline computed styles - critical for proper export
  function inlineStyles(element) {
    const computed = window.getComputedStyle(element);
    const styleProps = [
      'fill', 'stroke', 'stroke-width', 'stroke-opacity', 'opacity',
      'font-family', 'font-size', 'font-weight', 'text-anchor'
    ];
    
    styleProps.forEach(prop => {
      const value = computed.getPropertyValue(prop);
      if (value && value !== 'none' && value !== 'rgba(0, 0, 0, 0)') {
        const attrName = prop.replace(/-([a-z])/g, (g) => g[1].toUpperCase());
        element.setAttribute(attrName, value);
      }
    });
  }
  
  // Inline styles for all elements - this preserves styles during export
  const allElements = svgClone.querySelectorAll('*');
  allElements.forEach(el => {
    inlineStyles(el);
  });
  
  // Remove black strokes from nodes
  const nodeRects = svgClone.querySelectorAll('.node rect');
  nodeRects.forEach(rect => {
    const computed = window.getComputedStyle(rect);
    const stroke = computed.stroke;
    if (stroke === 'rgb(0, 0, 0)' || stroke === '#000' || stroke === 'black') {
      rect.setAttribute('stroke', 'none');
    }
  });
  
  // CRITICAL FIX: Set fill='none' on all links - SVG paths default to black fill!
  const links = svgClone.querySelectorAll('.link');
  links.forEach(link => {
    // THIS IS THE KEY FIX - SVG paths default to black fill if not set
    link.setAttribute('fill', 'none');
    
    const computed = window.getComputedStyle(link);
    const stroke = computed.stroke;
    const originalStroke = link.getAttribute('stroke');
    
    // Preserve the original colored stroke
    if (originalStroke && originalStroke !== '#000' && originalStroke !== 'black' && originalStroke !== 'rgb(0, 0, 0)') {
      link.setAttribute('stroke', originalStroke);
    } else if (stroke && stroke !== 'rgb(0, 0, 0)' && stroke !== '#000' && stroke !== 'black') {
      link.setAttribute('stroke', stroke);
    }
    
    // Ensure stroke-opacity is set
    const strokeOpacity = link.getAttribute('stroke-opacity') || computed.getPropertyValue('stroke-opacity') || '0.4';
    link.setAttribute('stroke-opacity', strokeOpacity);
    
    link.removeAttribute('filter');
  });
  
  // Remove shadow filters
  const defs = svgClone.querySelectorAll('defs');
  defs.forEach(def => {
    const filters = def.querySelectorAll('filter');
    filters.forEach(filter => {
      const filterId = filter.getAttribute('id');
      if (filterId && (filterId.includes('shadow') || filterId.includes('drop'))) {
        filter.remove();
      }
    });
  });
  
  // Get actual SVG dimensions
  const width = svg.width.baseVal.value || svg.getBoundingClientRect().width;
  const height = svg.height.baseVal.value || svg.getBoundingClientRect().height;
  
  // Ensure the clone has explicit dimensions
  svgClone.setAttribute('width', width);
  svgClone.setAttribute('height', height);
  svgClone.setAttribute('style', 'background: white;');
  
  // Serialize the cloned SVG with proper namespace
  const svgData = new XMLSerializer().serializeToString(svgClone);
  
  // Add XML declaration and ensure proper namespace
  const svgWithNamespace = '<?xml version="1.0" encoding="UTF-8"?>' +
    '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" ' +
    `width="${width}" height="${height}">` +
    '<rect width="100%" height="100%" fill="white"/>' +
    svgData.replace(/<svg[^>]*>/, '').replace('</svg>', '') +
    '</svg>';
  
  // Create canvas
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  
  // Set white background
  ctx.fillStyle = 'white';
  ctx.fillRect(0, 0, width, height);
  
  // Convert SVG to image
  const svgBlob = new Blob([svgWithNamespace], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(svgBlob);
  
  const img = new Image();
  img.onload = function() {
    ctx.drawImage(img, 0, 0, width, height);
    URL.revokeObjectURL(url);
    
    // Convert canvas to image data
    const imgData = canvas.toDataURL('image/png');
    
    // Create PDF - convert pixels to mm (1px = 0.264583mm at 96dpi)
    const { jsPDF } = window.jspdf;
    const widthMM = width * 0.264583;
    const heightMM = height * 0.264583;
    
    const pdf = new jsPDF({
      orientation: width > height ? 'landscape' : 'portrait',
      unit: 'mm',
      format: [widthMM, heightMM]
    });
    
    pdf.addImage(imgData, 'PNG', 0, 0, widthMM, heightMM);
    pdf.save('sankey_diagram.pdf');
  };
  img.onerror = function() {
    alert('Error exporting PDF. Please try again.');
    URL.revokeObjectURL(url);
  };
  img.src = url;
}

function populatePaperLists(included, excluded, overviewData) {
  const incSection = document.getElementById('includedSection');
  const excSection = document.getElementById('excludedSection');
  incSection.innerHTML = '';
  excSection.innerHTML = '';

  // Add search functionality for included papers
  const incSearchDiv = document.createElement('div');
  incSearchDiv.className = 'mb-3';
  incSearchDiv.innerHTML = `
    <div class="input-group">
      <span class="input-group-text">🔍</span>
      <input type="text" class="form-control" id="included-search" placeholder="Search included papers by title or author...">
    </div>
  `;
  incSection.appendChild(incSearchDiv);

  const incList = document.createElement('ul');
  incList.className = 'paper-list';
  incList.id = 'included-papers-list';
  incList.style.maxHeight = '600px';
  // Show DOI/URL and GitHub links for in-scope papers
  included.forEach(a => {
    const li = createPaperListItem(a, true, true); // showGithubLink=true, showDoiLink=true
    incList.appendChild(li);
  });
  incSection.appendChild(incList);

  // Add search functionality for excluded papers
  const excSearchDiv = document.createElement('div');
  excSearchDiv.className = 'mb-3';
  excSearchDiv.innerHTML = `
    <div class="input-group">
      <span class="input-group-text">🔍</span>
      <input type="text" class="form-control" id="excluded-search" placeholder="Search excluded papers by title or author...">
    </div>
  `;
  excSection.appendChild(excSearchDiv);

  // Create dropdown boxes for each exclusion reason using the same consolidated data as the table
  const categorizedExcluded = categorizeExcludedPapersFromConsolidatedData(overviewData, excluded);
  const excList = document.createElement('div');
  excList.id = 'excluded-papers-list';
  excList.style.maxHeight = '600px';
  excList.style.overflowY = 'auto';
  
  Object.entries(categorizedExcluded).forEach(([reason, data]) => {
    const categoryDiv = document.createElement('div');
    categoryDiv.className = 'mb-3';
    
    // Create dropdown header
    const dropdownHeader = document.createElement('div');
    dropdownHeader.className = 'dropdown-header d-flex justify-content-between align-items-center p-2 bg-light border rounded-top';
    dropdownHeader.style.cursor = 'pointer';
    dropdownHeader.innerHTML = `
      <h6 class="mb-0">${reason} <span class="badge bg-secondary">${data.count}</span></h6>
      <i class="fas fa-chevron-down dropdown-icon"></i>
    `;
    
    // Create dropdown content
    const dropdownContent = document.createElement('div');
    dropdownContent.className = 'dropdown-content border border-top-0 rounded-bottom';
    dropdownContent.style.display = 'none';
    dropdownContent.style.maxHeight = '400px';
    dropdownContent.style.overflowY = 'auto';
    
    const papersList = document.createElement('ul');
    papersList.className = 'paper-list mb-0';
    papersList.style.listStyle = 'none';
    papersList.style.padding = '0';
    data.papers.forEach(paper => {
      // Show DOI/URL for out-of-scope papers (no GitHub)
      const li = createPaperListItem(paper, false, true); // showGithubLink=false, showDoiLink=true
      li.style.padding = '8px 12px';
      li.style.borderBottom = '1px solid #eee';
      papersList.appendChild(li);
    });
    dropdownContent.appendChild(papersList);
    
    // Add click functionality for dropdown toggle
    dropdownHeader.addEventListener('click', function() {
      const content = this.nextElementSibling;
      const icon = this.querySelector('.dropdown-icon');
      
      if (content.style.display === 'none') {
        content.style.display = 'block';
        icon.className = 'fas fa-chevron-up dropdown-icon';
      } else {
        content.style.display = 'none';
        icon.className = 'fas fa-chevron-down dropdown-icon';
      }
    });
    
    categoryDiv.appendChild(dropdownHeader);
    categoryDiv.appendChild(dropdownContent);
    excList.appendChild(categoryDiv);
  });
  
  excSection.appendChild(excList);

  // Add search functionality
  setupSearch('included-search', 'included-papers-list', included);
  setupSearch('excluded-search', 'excluded-papers-list', excluded);
}

function categorizeExcludedPapers(excluded) {
  const categories = {};
  
  excluded.forEach(paper => {
    const criteria = extractExclusionCriteria(paper);
    if (criteria.length > 0) {
      // Count paper in all applicable categories (not just the first one)
      criteria.forEach(criterion => {
        const readableReason = getReadableExclusionReason(criterion);
        
        if (!categories[readableReason]) {
          categories[readableReason] = [];
        }
        // Only add the paper if it's not already in this category
        if (!categories[readableReason].some(p => p.article_id === paper.article_id)) {
          categories[readableReason].push(paper);
        }
      });
    } else {
      // Papers without explicit criteria
      if (!categories['No explicit criteria']) {
        categories['No explicit criteria'] = [];
      }
      categories['No explicit criteria'].push(paper);
    }
  });
  
  // Sort categories by count (descending)
  return Object.fromEntries(
    Object.entries(categories).sort((a, b) => b[1].length - a[1].length)
  );
}

function categorizeExcludedPapersFromOverview(overviewData, excluded) {
  // Get the breakdown from screening overview data and use the same consolidation logic
  const breakdown = overviewData.rayyan_screening.excluded_out_of_scope.breakdown.individual_criteria_counts;
  
  // Consolidate categories according to the same mapping used in populateOverview
  const consolidatedData = {};
  
  Object.entries(breakdown).forEach(([reason, info]) => {
    let consolidatedReason;
    
    // Map to consolidated categories (same logic as in populateOverview)
    if (reason === 'Survey/review paper' || reason === 'Review paper' || reason === 'Background article') {
      consolidatedReason = 'review/background article';
    } else if (reason === 'Other/Unclear' || reason === '__EXR__wrong outcome' || reason === '__EXR__engl' || reason === '__EXR__v') {
      consolidatedReason = 'No codebase/implementation';
    } else if (reason === '__EXR__no-fulltext') {
      consolidatedReason = 'no-fulltext';
    } else if (reason === '__EXR__not-in-english' || reason === '__EXR__foreign language') {
      consolidatedReason = 'not-in-english';
    } else {
      consolidatedReason = reason;
    }
    
    if (!consolidatedData[consolidatedReason]) {
      consolidatedData[consolidatedReason] = { count: 0, papers: [] };
    }
    consolidatedData[consolidatedReason].count += info.count;
  });
  
  // Now assign papers to categories based on their criteria
  const categories = {};
  excluded.forEach(paper => {
    const criteria = extractExclusionCriteria(paper);
    if (criteria.length > 0) {
      // Count paper in all applicable categories
      criteria.forEach(criterion => {
        const readableReason = getReadableExclusionReason(criterion);
        
        if (!categories[readableReason]) {
          categories[readableReason] = [];
        }
        // Only add the paper if it's not already in this category
        if (!categories[readableReason].some(p => p.article_id === paper.article_id)) {
          categories[readableReason].push(paper);
        }
      });
    } else {
      // Papers without explicit criteria
      if (!categories['No explicit criteria']) {
        categories['No explicit criteria'] = [];
      }
      categories['No explicit criteria'].push(paper);
    }
  });
  
  // Sort categories by count from screening overview (descending)
  return Object.fromEntries(
    Object.entries(categories).sort((a, b) => {
      const aCount = consolidatedData[a[0]] ? consolidatedData[a[0]].count : 0;
      const bCount = consolidatedData[b[0]] ? consolidatedData[b[0]].count : 0;
      return bCount - aCount;
    })
  );
}

function categorizeExcludedPapersFromConsolidatedData(overviewData, excluded) {
  // Use the exact same consolidation logic as the exclusion reason table
  const breakdown = overviewData.rayyan_screening.excluded_out_of_scope.breakdown.individual_criteria_counts;
  
  // Consolidate categories according to the same mapping used in populateOverview
  const consolidatedData = {};
  
  Object.entries(breakdown).forEach(([reason, info]) => {
    let consolidatedReason;
    
    // Map to consolidated categories (same logic as in populateOverview)
    if (reason === 'Survey/review paper' || reason === 'Review paper' || reason === 'Background article') {
      consolidatedReason = 'review/background article';
    } else if (reason === 'Other/Unclear' || reason === '__EXR__wrong outcome' || reason === '__EXR__engl' || reason === '__EXR__v') {
      consolidatedReason = 'No codebase/implementation';
    } else if (reason === '__EXR__no-fulltext') {
      consolidatedReason = 'no-fulltext';
    } else if (reason === '__EXR__not-in-english' || reason === '__EXR__foreign language') {
      consolidatedReason = 'not-in-english';
    } else {
      consolidatedReason = reason;
    }
    
    if (!consolidatedData[consolidatedReason]) {
      consolidatedData[consolidatedReason] = { count: 0, percentage: 0 };
    }
    consolidatedData[consolidatedReason].count += info.count;
    consolidatedData[consolidatedReason].percentage += info.percentage;
  });
  
  // Sort by count (descending) - same as exclusion reason table
  const sortedEntries = Object.entries(consolidatedData).sort((a, b) => b[1].count - a[1].count);
  
  // Map each paper to its consolidated categories
  const paperBuckets = {};
  excluded.forEach(paper => {
    const criteria = extractExclusionCriteria(paper);
    if (criteria.length > 0) {
      criteria.forEach(criterion => {
        const readableReason = getReadableExclusionReason(criterion);
        if (!paperBuckets[readableReason]) paperBuckets[readableReason] = [];
        if (!paperBuckets[readableReason].some(p => p.article_id === paper.article_id)) {
          paperBuckets[readableReason].push(paper);
        }
      });
    } else {
      if (!paperBuckets['No explicit criteria']) paperBuckets['No explicit criteria'] = [];
      paperBuckets['No explicit criteria'].push(paper);
    }
  });
  
  // Build final mapping with count from consolidated data and papers list
  return Object.fromEntries(
    sortedEntries.map(([reason, info]) => [reason, { count: info.count, papers: paperBuckets[reason] || [] }])
  );
}

function extractExclusionCriteria(article) {
  const criteria = [];
  
  if (article.customizations) {
    article.customizations.forEach(customization => {
      const key = customization.key;
      const value = customization.value;
      
      if (key.startsWith('"__EXR__') && value === '1') {
        criteria.push(key.replace(/"/g, ''));
      }
    });
  }
  
  return criteria;
}

function getReadableExclusionReason(criterion) {
  const reasonMap = {
    '__EXR__off-topic': 'Off-topic/Not neuro-symbolic',
    '__EXR__no-codebase': 'No codebase/implementation',
    '__EXR__survey': 'review/background article',
    '__EXR__background article': 'review/background article',
    '__EXR__not-research': 'Not research paper',
    '__EXR__no-eval': 'No evaluation',
    '__EXR__duplicate': 'Duplicate',
    '__EXR__review': 'review/background article',
    '__EXR__no-fulltext': 'no-fulltext',
    '__EXR__not-in-english': 'not-in-english',
    '__EXR__foreign language': 'not-in-english',
    '__EXR__c': 'No codebase/implementation',
    '__EXR__wrong outcome': 'No codebase/implementation',
    '__EXR__engl': 'No codebase/implementation',
    '__EXR__v': 'No codebase/implementation'
  };
  
  return reasonMap[criterion] || criterion;
}

function setupSearch(searchId, listId, allPapers) {
  const searchInput = document.getElementById(searchId);
  const listElement = document.getElementById(listId);
  
  searchInput.addEventListener('input', function() {
    const searchTerm = this.value.toLowerCase();
    
    if (listId === 'included-papers-list') {
      // Simple search for included papers
      const listItems = listElement.querySelectorAll('li');
      listItems.forEach(item => {
        const text = item.textContent.toLowerCase();
        item.style.display = text.includes(searchTerm) ? 'block' : 'none';
      });
    } else {
      // Search for excluded papers (dropdown structure)
      const categoryDivs = listElement.querySelectorAll('.mb-3');
      categoryDivs.forEach(categoryDiv => {
        const dropdownContent = categoryDiv.querySelector('.dropdown-content');
        const papersList = dropdownContent.querySelector('ul');
        const listItems = papersList.querySelectorAll('li');
        let hasVisibleItems = false;
        
        listItems.forEach(item => {
          const text = item.textContent.toLowerCase();
          const isVisible = text.includes(searchTerm);
          item.style.display = isVisible ? 'block' : 'none';
          if (isVisible) hasVisibleItems = true;
        });
        
        // Show/hide entire category based on whether it has visible items
        categoryDiv.style.display = hasVisibleItems ? 'block' : 'none';
      });
    }
  });
}

function populateFinalPaperLists(finalIncluded, finalExcluded) {
  const finalIncSection = document.getElementById('finalIncludedSection');
  const finalExcSection = document.getElementById('finalExcludedSection');
  finalIncSection.innerHTML = '';
  finalExcSection.innerHTML = '';

  // Add search functionality for final included papers
  const finalIncSearchDiv = document.createElement('div');
  finalIncSearchDiv.className = 'mb-3';
  finalIncSearchDiv.innerHTML = `
    <div class="input-group">
      <span class="input-group-text">🔍</span>
      <input type="text" class="form-control" id="final-included-search" placeholder="Search final included papers by title or author...">
    </div>
  `;
  finalIncSection.appendChild(finalIncSearchDiv);

  const finalIncList = document.createElement('ul');
  finalIncList.className = 'paper-list';
  finalIncList.id = 'final-included-papers-list';
  finalIncList.style.maxHeight = '600px';
  finalIncList.style.overflowY = 'auto';
  // Show DOI/URL and GitHub links for final included papers
  finalIncluded.forEach(a => {
    const li = createPaperListItem(a, true, true); // showGithubLink=true, showDoiLink=true
    finalIncList.appendChild(li);
  });
  finalIncSection.appendChild(finalIncList);

  // Add count summary
  const finalIncCount = document.createElement('p');
  finalIncCount.className = 'mt-3 text-muted';
  finalIncCount.textContent = `Total: ${finalIncluded.length} papers`;
  finalIncSection.appendChild(finalIncCount);

  // Add search functionality for final excluded papers
  const finalExcSearchDiv = document.createElement('div');
  finalExcSearchDiv.className = 'mb-3';
  finalExcSearchDiv.innerHTML = `
    <div class="input-group">
      <span class="input-group-text">🔍</span>
      <input type="text" class="form-control" id="final-excluded-search" placeholder="Search final excluded papers by title or author...">
    </div>
  `;
  finalExcSection.appendChild(finalExcSearchDiv);

  // Categorize excluded papers by exclusion reason
  const categorizedFinalExcluded = categorizeFinalExcludedPapers(finalExcluded);
  const finalExcList = document.createElement('div');
  finalExcList.id = 'final-excluded-papers-list';
  finalExcList.style.maxHeight = '600px';
  finalExcList.style.overflowY = 'auto';
  
  Object.entries(categorizedFinalExcluded).forEach(([reason, papers]) => {
    const categoryDiv = document.createElement('div');
    categoryDiv.className = 'mb-3';
    
    // Create dropdown header
    const dropdownHeader = document.createElement('div');
    dropdownHeader.className = 'dropdown-header d-flex justify-content-between align-items-center p-2 bg-light border rounded-top';
    dropdownHeader.style.cursor = 'pointer';
    dropdownHeader.innerHTML = `
      <h6 class="mb-0">${reason} <span class="badge bg-secondary">${papers.length}</span></h6>
      <i class="fas fa-chevron-down dropdown-icon"></i>
    `;
    
    // Create dropdown content
    const dropdownContent = document.createElement('div');
    dropdownContent.className = 'dropdown-content border border-top-0 rounded-bottom';
    dropdownContent.style.display = 'none';
    dropdownContent.style.maxHeight = '400px';
    dropdownContent.style.overflowY = 'auto';
    
    const papersList = document.createElement('ul');
    papersList.className = 'paper-list mb-0';
    papersList.style.listStyle = 'none';
    papersList.style.padding = '0';
    
    // Show GitHub link for "Missing Code" category
    const showGithub = reason === 'Missing Code';
    
    // Sort papers: those with repository_url first
    const sortedPapers = [...papers].sort((a, b) => {
      const aHasRepo = showGithub && (a.repository_url || (a.excel_data && (a.excel_data['Repository URL'] || a.excel_data['Repository URL '])));
      const bHasRepo = showGithub && (b.repository_url || (b.excel_data && (b.excel_data['Repository URL'] || b.excel_data['Repository URL '])));
      if (aHasRepo && !bHasRepo) return -1;
      if (!aHasRepo && bHasRepo) return 1;
      return 0;
    });
    
    sortedPapers.forEach(paper => {
      // Show DOI/URL for all final excluded papers, GitHub only for Missing Code category
      const li = createPaperListItem(paper, showGithub, true); // showGithubLink=showGithub, showDoiLink=true
      li.style.padding = '8px 12px';
      li.style.borderBottom = '1px solid #eee';
      papersList.appendChild(li);
    });
    dropdownContent.appendChild(papersList);
    
    // Add click functionality for dropdown toggle
    dropdownHeader.addEventListener('click', function() {
      const content = this.nextElementSibling;
      const icon = this.querySelector('.dropdown-icon');
      
      if (content.style.display === 'none') {
        content.style.display = 'block';
        icon.className = 'fas fa-chevron-up dropdown-icon';
      } else {
        content.style.display = 'none';
        icon.className = 'fas fa-chevron-down dropdown-icon';
      }
    });
    
    categoryDiv.appendChild(dropdownHeader);
    categoryDiv.appendChild(dropdownContent);
    finalExcList.appendChild(categoryDiv);
  });
  
  finalExcSection.appendChild(finalExcList);

  // Add count summary
  const finalExcCount = document.createElement('p');
  finalExcCount.className = 'mt-3 text-muted';
  finalExcCount.textContent = `Total: ${finalExcluded.length} papers`;
  finalExcSection.appendChild(finalExcCount);

  // Add search functionality
  setupFinalSearch('final-included-search', 'final-included-papers-list', finalIncluded);
  setupFinalSearch('final-excluded-search', 'final-excluded-papers-list', finalExcluded);
}

function categorizeFinalExcludedPapers(excluded) {
  const categories = {};
  
  // Expected counts from pie chart (for validation)
  // Note: "Partially Reproduced (Below Threshold)" removed as count is 0 (all such papers have "Include" in decision column)
  const expectedCounts = {
    'Missing Some Artifacts (not code, e.g. data, model, etc.)': 321,
    'Missing Code': 42,
    'Not Attempted - Off Topic': 30,
    'Has All Artifacts but Failed': 7,
    'Not Attempted - Background Article': 3,
    'Not Attempted - No Fulltext': 6,
    'Not Attempted - Not a Research Article': 1,
    'No quantitative evaluation': 21
  };
  
  excluded.forEach(paper => {
    let reason = 'Missing Some Artifacts (not code, e.g. data, model, etc.)'; // Default
    
    // First check if reproduction_category was set by generate_final_lists.py
    if (paper.reproduction_category) {
      reason = paper.reproduction_category;
      
      // Filter out papers that shouldn't be in excluded list
      // "Fully Reproduced" and "Partially Reproduced (Above Threshold)" should be in included list
      // "Partially Reproduced (Below Threshold)" papers with "Include" in decision column should also be in included list
      const reasonLower = reason.toLowerCase();
      if (reasonLower.includes('fully reproduced') || 
          (reasonLower.includes('partially reproduced') && reasonLower.includes('above')) ||
          (reasonLower.includes('partially reproduced') && reasonLower.includes('below'))) {
        // Skip this paper - it shouldn't be in excluded list
        return;
      }
    } else {
      // Fallback: infer from excel_data
      const excel = paper.excel_data || {};
      
      // Check exclusion reasons from screening (for "not attempted" categories)
      const isOffTopic = excel['Does the paper discuss Neuro-Symbolic AI'] || '';
      const isOffTopicLower = String(isOffTopic).toLowerCase();
      const isBackground = excel['The paper is Not a Review'] || '';
      const isBackgroundLower = String(isBackground).toLowerCase();
      const isResearch = excel['Does the paper present an original research study?'] || '';
      const isResearchLower = String(isResearch).toLowerCase();
      const hasFulltext = excel['Is the Full Text available for the paper?'] || '';
      const hasFulltextLower = String(hasFulltext).toLowerCase();
      
      // Check reproduction status
      const reproStatus = excel['Were the results reproduced? (did the results obtained match (from full to partial) the reported results from the paper)'] || '';
      const reproStatusLower = String(reproStatus).toLowerCase();
      const isReproducible = excel['Is the study reproducible (is the codebase AND data AND model artifacts required to reproduce publicly available)? '] || '';
      const isReproducibleLower = String(isReproducible).toLowerCase();
      const hasCodebase = excel['The paper has an associated codebase'] || '';
      const hasCodebaseLower = String(hasCodebase).toLowerCase();
      
      // Check quantitative evaluation (exclusion reason)
      const hasQuantEval = excel['Does the paper include a Quantitative Evaluation'] || '';
      const hasQuantEvalLower = String(hasQuantEval).toLowerCase();
      
      // Categorize (matching pie chart logic)
      // First check quantitative evaluation (exclusion reason)
      if (hasQuantEvalLower === 'no' || hasQuantEvalLower === 'n' || hasQuantEvalLower === 'false' || hasQuantEvalLower === '0') {
        reason = 'No quantitative evaluation';
      } else if (isOffTopicLower === 'no') {
        reason = 'Not Attempted - Off Topic';
      } else if (isBackgroundLower === 'no') {
        reason = 'Not Attempted - Background Article';
      } else if (isResearchLower === 'no') {
        reason = 'Not Attempted - Not a Research Article';
      } else if (hasFulltextLower === 'no') {
        reason = 'Not Attempted - No Fulltext';
      } else if (hasCodebaseLower === 'no') {
        reason = 'Missing Code';
      } else if (reproStatusLower.includes('partial') && reproStatusLower.includes('below')) {
        reason = 'Partially Reproduced (Below Threshold)';
      } else if (reproStatusLower.includes('partial') && reproStatusLower.includes('above')) {
        reason = 'Partially Reproduced (Above Threshold)';
      } else if (isReproducibleLower === 'yes' && (reproStatusLower === 'no' || reproStatusLower.includes('failed'))) {
        reason = 'Has All Artifacts but Failed';
      } else if (isReproducibleLower === 'no' && hasCodebaseLower === 'yes') {
        reason = 'Missing Some Artifacts (not code, e.g. data, model, etc.)';
      } else if (reproStatusLower === 'no' || reproStatusLower.includes('not reproduced')) {
        reason = 'Missing Some Artifacts (not code, e.g. data, model, etc.)';
      }
    }
    
    // Normalize reason to match pie chart categories
    reason = normalizeExclusionReasonForFinalExcluded(reason);
    
    // Skip if reason is null (filtered out categories)
    if (!reason) {
      return;
    }
    
    if (!categories[reason]) {
      categories[reason] = [];
    }
    categories[reason].push(paper);
  });
  
  // Sort categories by count (descending)
  return Object.fromEntries(
    Object.entries(categories).sort((a, b) => b[1].length - a[1].length)
  );
}

function normalizeExclusionReasonForFinalExcluded(reason) {
  // Map to match pie chart categories exactly
  const reasonLower = reason.toLowerCase();
  
  // Filter out categories that shouldn't be in excluded list
  if (reasonLower.includes('fully reproduced') || 
      (reasonLower.includes('partially reproduced') && reasonLower.includes('above')) ||
      (reasonLower.includes('partially reproduced') && reasonLower.includes('below'))) {
    // These should be in included list, not excluded
    return null; // Will be filtered out
  }
  
  if (reasonLower.includes('missing some artifacts') || reasonLower.includes('missing artifacts')) {
    return 'Missing Some Artifacts (not code, e.g. data, model, etc.)';
  } else if (reasonLower.includes('missing code') || reasonLower.includes('no code')) {
    return 'Missing Code';
  } else if (reasonLower.includes('has all artifacts but failed') || reasonLower.includes('all artifacts but failed')) {
    return 'Has All Artifacts but Failed';
  } else if (reasonLower.includes('not attempted') && reasonLower.includes('off topic')) {
    return 'Not Attempted - Off Topic';
  } else if (reasonLower.includes('not attempted') && reasonLower.includes('background')) {
    return 'Not Attempted - Background Article';
  } else if (reasonLower.includes('not attempted') && reasonLower.includes('no fulltext')) {
    return 'Not Attempted - No Fulltext';
  } else if (reasonLower.includes('not attempted') && reasonLower.includes('not a research')) {
    return 'Not Attempted - Not a Research Article';
  } else if (reasonLower.includes('no quantitative evaluation') || reasonLower.includes('quantitative evaluation') && reasonLower.includes('no')) {
    return 'No quantitative evaluation';
  } else if (reasonLower.includes('off topic') || reasonLower.includes('not neuro-symbolic')) {
    return 'Not Attempted - Off Topic';
  } else if (reasonLower.includes('background') || reasonLower.includes('review')) {
    return 'Not Attempted - Background Article';
  } else if (reasonLower.includes('no fulltext') || reasonLower.includes('no full text')) {
    return 'Not Attempted - No Fulltext';
  } else if (reasonLower.includes('not research') || reasonLower.includes('not a research')) {
    return 'Not Attempted - Not a Research Article';
  }
  
  return reason;
}

function normalizeExclusionReason(reason) {
  if (!reason || reason === 'N/A' || reason === '') {
    return 'Excluded (reason not specified)';
  }
  
  const reasonLower = reason.toLowerCase();
  
  // Map common exclusion reasons to match pie chart categories
  if (reasonLower.includes('missing code') || reasonLower.includes('no code')) {
    return 'Missing Code';
  } else if (reasonLower.includes('missing artifact') || reasonLower.includes('missing some artifact') || reasonLower.includes('missing some artifacts')) {
    return 'Missing Some Artifacts';
  } else if (reasonLower.includes('partial') && reasonLower.includes('below threshold')) {
    return 'Partially Reproduced (Below Threshold)';
  } else if (reasonLower.includes('has all artifacts but failed') || reasonLower.includes('all artifacts but failed')) {
    return 'Has All Artifacts but Failed';
  } else if (reasonLower.includes('off topic') || reasonLower.includes('not neuro-symbolic')) {
    return 'Off Topic / Not Neuro-Symbolic';
  } else if (reasonLower.includes('background') || reasonLower.includes('review') || reasonLower.includes('survey')) {
    return 'Review/Background Article';
  } else if (reasonLower.includes('no fulltext') || reasonLower.includes('no full text')) {
    return 'No Fulltext Available';
  } else if (reasonLower.includes('not research') || reasonLower.includes('not a research')) {
    return 'Not a Research Article';
  } else if (reasonLower.includes('not reproduceable') || reasonLower.includes('not reproduced') || reasonLower.includes('reproduction failed')) {
    return 'The reported results were not reproduceable';
  }
  
  // Return as-is if already properly formatted
  return reason;
}

function setupFinalSearch(searchId, listId, allPapers) {
  const searchInput = document.getElementById(searchId);
  if (!searchInput) return;
  
  const listElement = document.getElementById(listId);
  if (!listElement) return;
  
  searchInput.addEventListener('input', function() {
    const searchTerm = this.value.toLowerCase();
    
    if (listId === 'final-included-papers-list') {
      // Simple search for included papers
      const listItems = listElement.querySelectorAll('li');
      listItems.forEach(item => {
        const text = item.textContent.toLowerCase();
        item.style.display = text.includes(searchTerm) ? 'block' : 'none';
      });
    } else {
      // Search for excluded papers (dropdown structure)
      const categoryDivs = listElement.querySelectorAll('.mb-3');
      categoryDivs.forEach(categoryDiv => {
        const dropdownContent = categoryDiv.querySelector('.dropdown-content');
        if (!dropdownContent) return;
        const papersList = dropdownContent.querySelector('ul');
        if (!papersList) return;
        const listItems = papersList.querySelectorAll('li');
        let hasVisibleItems = false;
        
        listItems.forEach(item => {
          const text = item.textContent.toLowerCase();
          const isVisible = text.includes(searchTerm);
          item.style.display = isVisible ? 'block' : 'none';
          if (isVisible) hasVisibleItems = true;
        });
        
        // Show/hide entire category based on whether it has visible items
        categoryDiv.style.display = hasVisibleItems ? 'block' : 'none';
      });
    }
  });
}

// kick off
init(); 