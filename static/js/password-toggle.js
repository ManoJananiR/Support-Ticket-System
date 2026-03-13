document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('input[type="password"]').forEach(function(field) {
        // Skip if already processed
        if (field.dataset.passwordToggle) return;
        field.dataset.passwordToggle = 'true';
        
        // Create wrapper
        const wrapper = document.createElement('div');
        wrapper.style.position = 'relative';
        wrapper.style.width = '100%';
        
        field.parentNode.insertBefore(wrapper, field);
        wrapper.appendChild(field);
        
        // Create button with explicit HTML
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.innerHTML = '🔒'; // Using emoji as fallback
        btn.style.position = 'absolute';
        btn.style.right = '10px';
        btn.style.top = '50%';
        btn.style.transform = 'translateY(-50%)';
        btn.style.background = 'none';
        btn.style.border = 'none';
        btn.style.cursor = 'pointer';
        btn.style.fontSize = '16px';
        
        wrapper.appendChild(btn);
        field.style.paddingRight = '35px';
        
        btn.addEventListener('click', function() {
            if (field.type === 'password') {
                field.type = 'text';
                btn.innerHTML = '🔓';
            } else {
                field.type = 'password';
                btn.innerHTML = '🔒';
            }
        });
    });
});