// Helper to create list items
function createPaperListItem(article) {
  const li = document.createElement('li');
  const title = article.title || '(Untitled)';
  const link = article.url ? `<a href="${article.url}" target="_blank" rel="noopener">${title}</a>` : title;
  li.innerHTML = `${link} <span class="text-muted small">(${article.year || 'n.d.'})</span>`;
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
    populatePaperLists(includeData, excludeData);
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

  // Inclusion criteria
  const incHeader = document.createElement('h5');
  incHeader.textContent = 'Inclusion Criteria';
  section.appendChild(incHeader);
  const incList = document.createElement('ul');
  data.inclusion_criteria.forEach(c => {
    const li = document.createElement('li');
    li.textContent = `${c.name}: ${c.description}`;
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
  Object.entries(breakdown).forEach(([reason, info]) => {
    labels.push(reason);
    counts.push(info.count);
    const row = document.createElement('tr');
    row.innerHTML = `<td>${reason}</td><td>${info.count}</td><td>${info.percentage}%</td>`;
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

function populatePaperLists(included, excluded) {
  const incSection = document.getElementById('includedSection');
  const excSection = document.getElementById('excludedSection');
  incSection.innerHTML = '';
  excSection.innerHTML = '';

  const incList = document.createElement('ul');
  incList.className = 'paper-list';
  included.forEach(a => incList.appendChild(createPaperListItem(a)));
  incSection.appendChild(incList);

  const excList = document.createElement('ul');
  excList.className = 'paper-list';
  excluded.forEach(a => excList.appendChild(createPaperListItem(a)));
  excSection.appendChild(excList);
}

// kick off
init(); 