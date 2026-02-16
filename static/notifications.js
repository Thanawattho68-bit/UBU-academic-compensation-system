document.addEventListener("DOMContentLoaded", function () {
    const sidebarBadge = document.getElementById("sidebar-notif-badge");

    function fetchNotifications() {
        fetch('/api/notifications')
            .then(response => response.json())
            .then(data => {
                if (data.length > 0) {
                    if (sidebarBadge) {
                        sidebarBadge.style.display = "inline-block";
                        sidebarBadge.innerText = data.length > 99 ? "99+" : data.length;
                    }
                } else {
                    if (sidebarBadge) sidebarBadge.style.display = "none";
                }
            })
            .catch(err => console.error("Error loading notifications", err));
    }

    // Initial Fetch
    fetchNotifications();
    
    // Poll every 10s
    setInterval(fetchNotifications, 10000);
});
