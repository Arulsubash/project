//Login Form
function login(event) {
    let student = document.querySelector("#student-containner");
    let admin = document.querySelector("#admin-containner");
    let worker = document.querySelector("#worker-containner");
    let register = document.querySelector("#student-registration");

    if(event.target.textContent == "Enter as Student") {
        student.style.display = "flex";
    }
    else if(event.target.textContent == "Enter as Admin") {
        admin.style.display = "flex";
    }
    else if(event.target.textContent == "Enter as Worker") {
        worker.style.display = "flex";
    }
    else if(event.target.textContent == "click here") {
        student.style.display = "none";
        register.style.display = "flex";
    }
}

//Student request button function
function request() {
    let request = document.querySelector("#student-request");
    request.style.display = "flex";
}

// Close modal function
function closeModal(modalId) {
    document.getElementById(modalId).style.display = "none";
}

// Close modal when clicking outside
document.addEventListener('click', function(event) {
    const studentContainer = document.getElementById('student-containner');
    const adminContainer = document.getElementById('admin-containner');
    const workerContainer = document.getElementById('worker-containner');
    const studentRegistration = document.getElementById('student-registration');
    const studentRequest = document.getElementById('student-request');
    
    if (studentContainer && event.target === studentContainer) {
        studentContainer.style.display = 'none';
    }
    if (adminContainer && event.target === adminContainer) {
        adminContainer.style.display = 'none';
    }
    if (workerContainer && event.target === workerContainer) {
        workerContainer.style.display = 'none';
    }
    if (studentRegistration && event.target === studentRegistration) {
        studentRegistration.style.display = 'none';
    }
    if (studentRequest && event.target === studentRequest) {
        studentRequest.style.display = 'none';
    }
});

// Close modal with Escape key
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        const modals = [
            'student-containner', 
            'admin-containner', 
            'worker-containner', 
            'student-registration', 
            'student-request'
        ];
        
        modals.forEach(modalId => {
            const modal = document.getElementById(modalId);
            if (modal && modal.style.display === 'flex') {
                modal.style.display = 'none';
            }
        });
    }
});

// Iterate & Display Requests
document.addEventListener("DOMContentLoaded", () => {
    if (window.requests) {
        const container = document.getElementById("request-box");
        container.innerHTML = "";
        
        // class for uniform height
        container.classList.add("request-grid");

        window.requests.forEach((req) => {
            const card = document.createElement("div");
            card.classList.add("col-12", "col-md-6", "col-lg-6");
            card.style.zIndex = "1";
            
            let statusColorClass = "";
            let statusIconClass = "";

            if (req.status === "Pending") {
                statusColorClass = "bg-secondary";
                statusIconClass = "bi-exclamation-circle";
            } else if (req.status === "In Progress") {
                statusColorClass = "bg-primary";
                statusIconClass = "bi-hourglass-split";
            } else if (req.status === "Completed") {
                statusColorClass = "bg-success";
                statusIconClass = "bi-check-circle";
            } else {
                statusColorClass = "bg-info";
                statusIconClass = "bi-question-circle";
            }


            let imageHtml = '';
            if (req.image_path) {
                imageHtml = `
                    <button class="btn btn-secondary btn-sm" data-bs-toggle="modal" data-bs-target="#imageModal" data-image-path="${req.image_path}">
                        <i class="bi bi-paperclip"></i> View Attachment
                    </button>
                `;
            }

            card.innerHTML = `
                <div class="card shadow-sm border-0" style="margin-bottom: 50px;">
                    <div class="card-body">
                        <div class="d-flex w-100">
                           <h5 class="card-title mb-1">
                               ${req.title}
                           </h5>
                           <span class="badge ${statusColorClass} text-dark ms-auto" style="border-radius: 1000px;">
                               <i class="text-white ${statusIconClass}"></i> ${req.status}
                           </span>
                        </div>
                        <p class="text-muted mb-3">${req.description}</p>
                        <p class="mb-1"><i class="bi bi-geo-alt"></i> ${req.location}</p>
                        <p class="mb-1"><i class="bi bi-clock"></i> ${req.date}</p>
                        <p class="mb-0"><i class="bi bi-person"></i> You &nbsp;&nbsp;
                        <span class="text-primary">Priority: ${req.priority}</span></p>
                        ${imageHtml}
                    </div>
                </div>
            `;
            container.append(card);
        });
    }
});

// Image Modal Event Listener
document.getElementById('imageModal').addEventListener('show.bs.modal', function (event) {
    const button = event.relatedTarget;
    const imagePath = button.getAttribute('data-image-path');
    const modalImage = this.querySelector('#modalImage');
    
    if (imagePath) {
        modalImage.src = `/static/uploads/${imagePath}`;
    }
});


//search:
document.getElementById("input").addEventListener("keyup", function () {
    const searchTerm = this.value.toLowerCase();
    const requestBox = document.getElementById("request-box");
    const cards = requestBox.querySelectorAll(".card");

    cards.forEach((card) => {
        const content = card.textContent.toLowerCase();
        card.parentElement.style.display = content.includes(searchTerm) ? "block" : "none";
    });
});

//filter
function applyFilters() {
  const searchTerm = document.getElementById("input").value.toLowerCase();
  const filterValue = document.getElementById("filterDropdown").getAttribute("data-selected") || "all";
  const cards = document.querySelectorAll("#request-box .card");

  cards.forEach((card) => {
    const text = card.textContent.toLowerCase();

    const matchesSearch = text.includes(searchTerm);
    let matchesFilter = true;

    if (filterValue === "pending") {
      matchesFilter = text.includes("pending");
    } else if (filterValue === "in progress") {
      matchesFilter = text.includes("in progress");
    } else if (filterValue === "completed") {
      matchesFilter = text.includes("completed");
    } else if (["low", "medium", "high"].includes(filterValue)) {
      matchesFilter = text.includes(`priority: ${filterValue}`);
    }

    card.parentElement.style.display = (matchesSearch && matchesFilter) ? "block" : "none";
  });
}

document.querySelectorAll(".filter-option").forEach((item) => {
  item.addEventListener("click", function () {
    const filterValue = this.getAttribute("data-filter").toLowerCase();
    const label = this.textContent;

    document.getElementById("selected-filter").textContent = label;
    document.getElementById("filterDropdown").setAttribute("data-selected", filterValue);

    applyFilters();
  });
});

document.getElementById("input").addEventListener("keyup", applyFilters);

// Auto-dismiss flash messages 
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert');
    
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
});

// Handle add worker form submission
document.addEventListener('DOMContentLoaded', function() {
    const addWorkerForm = document.getElementById('addWorkerForm');
    if (addWorkerForm) {
        addWorkerForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            
            fetch('/add-worker', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (response.redirected) {
                    window.location.href = response.url;
                } else {
                    return response.text();
                }
            })
            .then(data => {
                if (data) {
                    alert('Error: ' + data);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred while adding the worker.');
            });
        });
    }
});

// Search functionality for worker tasks
document.addEventListener('DOMContentLoaded', function() {
    const workerSearchInput = document.getElementById("worker-search-input");
    if (workerSearchInput) {
        workerSearchInput.addEventListener("keyup", function() {
            const searchTerm = this.value.toLowerCase();
            const taskCards = document.querySelectorAll(".task-card");
            
            taskCards.forEach(card => {
                const text = card.textContent.toLowerCase();
                card.style.display = text.includes(searchTerm) ? "block" : "none";
            });
        });
    }
});

// Filter functionality for worker tasks
document.addEventListener('DOMContentLoaded', function() {
    const filterOptions = document.querySelectorAll(".worker-filter-option");
    if (filterOptions.length > 0) {
        filterOptions.forEach(item => {
            item.addEventListener("click", function() {
                const filterValue = this.getAttribute("data-filter").toLowerCase();
                document.getElementById("worker-selected-filter").textContent = this.textContent;
                
                const taskCards = document.querySelectorAll(".task-card");
                
                taskCards.forEach(card => {
                    const status = card.querySelector(".badge").textContent.toLowerCase();
                    const priority = card.querySelector(".text-danger, .text-warning, .text-info").textContent.toLowerCase();
                    
                    let showCard = true;
                    
                    if (filterValue !== "all") {
                        if (["pending", "in progress", "completed"].includes(filterValue)) {
                            showCard = status.includes(filterValue);
                        } else if (["low", "medium", "high"].includes(filterValue)) {
                            showCard = priority.includes(filterValue);
                        }
                    }
                    
                    card.style.display = showCard ? "block" : "none";
                });
            });
        });
    }
});

// Send status update email
function sendStatusUpdate(requestId) {
    fetch('/send-status-update/' + requestId, {
        method: 'POST'
    })
    .then(response => {
        if (response.redirected) {
            window.location.href = response.url;
        }
    });
}