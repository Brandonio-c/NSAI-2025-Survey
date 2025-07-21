// Helper to create list items
function createPaperListItem(article) {
  const li = document.createElement('li');
  const title = article.title || '(Untitled)';
  const link = article.url ? `<a href="${article.url}" target="_blank" rel="noopener">${title}</a>` : title;
  const author = article.author || '';
  const year = article.year || 'n.d.';
  
  li.innerHTML = `
    <div>
      <strong>${link}</strong>
      <br>
      <small class="text-muted">
        ${author ? `Authors: ${author} • ` : ''}Year: ${year}
        ${article.article_id ? `• ID: ${article.article_id}` : ''}
      </small>
    </div>
  `;
  return li;
}

async function loadJSON(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Failed to load ${path}`);
  return response.json();
}

async function init() {
  try {
    const [criteriaData, overviewData, includeData, excludeData] = await Promise.all([
      loadJSON('data/inclusion_exclusion_criteria.json'),
      loadJSON('data/screening_overview_enriched.json'),
      loadJSON('data/include.json'),
      loadJSON('data/exclude.json')
    ]);

    populateCriteria(criteriaData);
    populateOverview(overviewData);
    populatePaperLists(includeData, excludeData, overviewData);
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
  const includedCount = screening.included_within_scope;
  const excludedCount = screening.excluded_out_of_scope.total_count || screening.excluded_out_of_scope;

  const summary = document.createElement('p');
  summary.innerHTML = `<strong>Total included:</strong> ${includedCount} &nbsp;&nbsp;|&nbsp;&nbsp; <strong>Total excluded:</strong> ${excludedCount}`;
  section.appendChild(summary);

  // Add Sankey diagram
  const sankeyDiv = document.createElement('div');
  sankeyDiv.className = 'mt-4 mb-4';
  sankeyDiv.innerHTML = '<h5>Screening Flow Diagram</h5>';
  const sankeyContainer = document.createElement('div');
  sankeyContainer.id = 'sankey-container';
  sankeyContainer.style.height = '400px';
  sankeyDiv.appendChild(sankeyContainer);
  section.appendChild(sankeyDiv);

  // Create Sankey diagram
  createSankeyDiagram(data);

  // Pie chart canvas
  const canvas = document.createElement('canvas');
  canvas.id = 'exclusionPie';
  canvas.height = 300;
  section.appendChild(canvas);

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
      consolidatedReason = 'review / background article / survey (no novel method presented)';
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

  // Render pie chart
  new Chart(canvas, {
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
        legend: { position: 'bottom' }
      }
    }
  });
}

function createSankeyDiagram(data) {
  const searchData = data.search_and_deduplication;
  const screening = data.rayyan_screening;
  
  const totalHits = searchData.total_results_retrieved;
  const afterDedup = searchData.after_dedup_rayyan;
  const included = screening.included_within_scope;
  const excluded = screening.excluded_out_of_scope.total_count || screening.excluded_out_of_scope;
  const duplicatesRemoved = totalHits - afterDedup;

  // Get exclusion breakdown and consolidate categories
  const exclusionBreakdown = screening.excluded_out_of_scope.breakdown.individual_criteria_counts;
  
  // Consolidate categories for Sankey diagram
  const consolidatedBreakdown = {};
  Object.entries(exclusionBreakdown).forEach(([reason, info]) => {
    let consolidatedReason;
    
    if (reason === 'Survey/review paper' || reason === 'Review paper' || reason === 'Background article') {
      consolidatedReason = 'review / background article / survey (no novel method presented)';
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
      consolidatedBreakdown[consolidatedReason] = { count: 0 };
    }
    consolidatedBreakdown[consolidatedReason].count += info.count;
  });
  
  const topExclusionReasons = Object.entries(consolidatedBreakdown)
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 5); // Top 5 reasons

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
  }

  // Create the final Sankey data object
  const sankeyData = { nodes, links };

  // Set up the SVG
  const container = document.getElementById('sankey-container');
  const width = container.offsetWidth || 800;
  const height = 400;
  const margin = { top: 20, right: 20, bottom: 20, left: 20 };

  // Clear any existing SVG
  d3.select('#sankey-container').selectAll('*').remove();

  const svg = d3.select('#sankey-container')
    .append('svg')
    .attr('width', width)
    .attr('height', height)
    .append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`);

  // Color scale
  const color = d3.scaleOrdinal(d3.schemeCategory10);

  // Create the Sankey layout
  const sankey = d3.sankey()
    .nodeWidth(15)
    .nodePadding(10)
    .extent([[1, 1], [width - margin.left - margin.right - 1, height - margin.top - margin.bottom - 5]]);

  // Apply the layout
  const { nodes: layoutNodes, links: layoutLinks } = sankey({
    nodes: sankeyData.nodes.map(d => Object.assign({}, d)),
    links: sankeyData.links.map(d => Object.assign({}, d))
  });

  // Add the links
  svg.append('g')
    .selectAll('path')
    .data(layoutLinks)
    .join('path')
    .attr('class', 'link')
    .attr('d', d3.sankeyLinkHorizontal())
    .attr('stroke', d => color(d.source.id))
    .attr('stroke-width', d => Math.max(1, d.width))
    .style('stroke-opacity', 0.5)
    .on('mouseover', function(event, d) {
      d3.select(this).style('stroke-opacity', 0.8);
    })
    .on('mouseout', function(event, d) {
      d3.select(this).style('stroke-opacity', 0.5);
    });

  // Add the nodes
  const node = svg.append('g')
    .selectAll('g')
    .data(layoutNodes)
    .join('g')
    .attr('class', 'node');

  node.append('rect')
    .attr('x', d => d.x0)
    .attr('y', d => d.y0)
    .attr('height', d => d.y1 - d.y0)
    .attr('width', d => d.x1 - d.x0)
    .attr('fill', d => color(d.id))
    .attr('stroke', '#000');

  // Add the node labels
  node.append('text')
    .attr('x', d => d.x0 < (width - margin.left - margin.right) / 2 ? d.x1 + 6 : d.x0 - 6)
    .attr('y', d => (d.y1 + d.y0) / 2)
    .attr('dy', '0.35em')
    .attr('text-anchor', d => d.x0 < (width - margin.left - margin.right) / 2 ? 'start' : 'end')
    .style('font-size', '12px')
    .text(d => d.name);

  // Add value labels on the links
  svg.append('g')
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
  included.forEach(a => incList.appendChild(createPaperListItem(a)));
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

  // Create dropdown boxes for each exclusion reason using screening overview data
  const categorizedExcluded = categorizeExcludedPapersFromOverview(overviewData, excluded);
  const excList = document.createElement('div');
  excList.id = 'excluded-papers-list';
  excList.style.maxHeight = '600px';
  excList.style.overflowY = 'auto';
  
  Object.entries(categorizedExcluded).forEach(([reason, papers]) => {
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
    papers.forEach(paper => {
      const li = createPaperListItem(paper);
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
  const categories = {};
  
  // Get the breakdown from screening overview data
  const breakdown = overviewData.rayyan_screening.excluded_out_of_scope.breakdown.individual_criteria_counts;
  
  // Consolidate categories according to the same mapping used in populateOverview
  const consolidatedData = {};
  
  Object.entries(breakdown).forEach(([reason, info]) => {
    let consolidatedReason;
    
    // Map to consolidated categories (same logic as in populateOverview)
    if (reason === 'Survey/review paper' || reason === 'Review paper' || reason === 'Background article') {
      consolidatedReason = 'review / background article / survey (no novel method presented)';
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
    '__EXR__survey': 'review / background article / survey (no novel method presented)',
    '__EXR__background article': 'review / background article / survey (no novel method presented)',
    '__EXR__not-research': 'Not research paper',
    '__EXR__no-eval': 'No evaluation',
    '__EXR__duplicate': 'Duplicate',
    '__EXR__review': 'review / background article / survey (no novel method presented)',
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

// kick off
init(); 