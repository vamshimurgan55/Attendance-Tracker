// static/live_time.js

document.addEventListener('DOMContentLoaded', function() {
    function updateLiveTime() {
        const now = new Date();
        // Format options for a readable date and time, including seconds and AM/PM
        const options = {
            weekday: 'short', // e.g., Mon
            month: 'short',   // e.g., Jun
            day: 'numeric',   // e.g., 09
            year: 'numeric',  // e.g., 2025
            hour: 'numeric',  // e.g., 04
            minute: 'numeric',// e.g., 41
            second: 'numeric',// e.g., 11
            hour12: true      // Use 12-hour format with AM/PM
        };
        const formattedDateTime = now.toLocaleString('en-US', options); // 'en-US' for standard English formatting

        // Find the element with the ID 'live-time-display' and update it
        const liveTimeElement = document.getElementById('live-time-display');
        if (liveTimeElement) {
            liveTimeElement.textContent = formattedDateTime;
        }
    }

    // Update time immediately on page load
    updateLiveTime();

    // Update time every second
    setInterval(updateLiveTime, 1000);
});