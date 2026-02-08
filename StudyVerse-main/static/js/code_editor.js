// Code Editor Enhancements for Byte Battle
// Adds auto-indentation and smart formatting

document.addEventListener('DOMContentLoaded', () => {
    const codeEditor = document.getElementById('code-editor');
    if (!codeEditor) return;

    // Auto-indent on Enter key
    codeEditor.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();

            const start = this.selectionStart;
            const end = this.selectionEnd;
            const value = this.value;

            // Get the current line
            const lineStart = value.lastIndexOf('\n', start - 1) + 1;
            const currentLine = value.substring(lineStart, start);

            // Count leading spaces/tabs
            const indent = currentLine.match(/^[\s\t]*/)[0];

            // Check if line ends with colon (Python, etc.) or opening brace (C++, Java, etc.)
            const shouldIncreaseIndent = /[:{(\[][\s]*$/.test(currentLine.trimEnd());

            // Calculate new indent
            let newIndent = indent;
            if (shouldIncreaseIndent) {
                // Add 4 spaces (or 1 tab) for new indent level
                newIndent += '    '; // 4 spaces
            }

            // Insert newline with proper indentation
            const newValue = value.substring(0, start) + '\n' + newIndent + value.substring(end);
            this.value = newValue;

            // Set cursor position after the indent
            const newCursorPos = start + 1 + newIndent.length;
            this.selectionStart = this.selectionEnd = newCursorPos;
        }

        // Tab key handling (insert 4 spaces instead of tab character)
        else if (e.key === 'Tab') {
            e.preventDefault();

            const start = this.selectionStart;
            const end = this.selectionEnd;
            const value = this.value;

            if (start === end) {
                // No selection - insert 4 spaces
                const spaces = '    ';
                this.value = value.substring(0, start) + spaces + value.substring(end);
                this.selectionStart = this.selectionEnd = start + spaces.length;
            } else {
                // Selection exists - indent/dedent entire lines
                if (e.shiftKey) {
                    // Shift+Tab - Dedent
                    dedentSelection(this, start, end);
                } else {
                    // Tab - Indent
                    indentSelection(this, start, end);
                }
            }
        }

        // Backspace - smart dedent
        else if (e.key === 'Backspace') {
            const start = this.selectionStart;
            const end = this.selectionEnd;
            const value = this.value;

            // Only do smart dedent if no selection and cursor is after spaces
            if (start === end && start > 0) {
                const lineStart = value.lastIndexOf('\n', start - 1) + 1;
                const beforeCursor = value.substring(lineStart, start);

                // Check if we're at the end of indentation (only spaces before cursor)
                if (/^[\s]+$/.test(beforeCursor) && beforeCursor.length > 0) {
                    e.preventDefault();

                    // Remove up to 4 spaces (one indent level)
                    const spacesToRemove = Math.min(4, beforeCursor.length - (beforeCursor.length % 4 || 4));
                    const newValue = value.substring(0, start - spacesToRemove) + value.substring(end);
                    this.value = newValue;
                    this.selectionStart = this.selectionEnd = start - spacesToRemove;
                }
            }
        }
    });

    // Indent selected lines
    function indentSelection(editor, start, end) {
        const value = editor.value;
        const lineStart = value.lastIndexOf('\n', start - 1) + 1;
        const lineEnd = value.indexOf('\n', end);
        const actualEnd = lineEnd === -1 ? value.length : lineEnd;

        const selectedText = value.substring(lineStart, actualEnd);
        const indentedText = selectedText.split('\n').map(line => '    ' + line).join('\n');

        editor.value = value.substring(0, lineStart) + indentedText + value.substring(actualEnd);

        // Adjust selection
        editor.selectionStart = lineStart;
        editor.selectionEnd = lineStart + indentedText.length;
    }

    // Dedent selected lines
    function dedentSelection(editor, start, end) {
        const value = editor.value;
        const lineStart = value.lastIndexOf('\n', start - 1) + 1;
        const lineEnd = value.indexOf('\n', end);
        const actualEnd = lineEnd === -1 ? value.length : lineEnd;

        const selectedText = value.substring(lineStart, actualEnd);
        const dedentedText = selectedText.split('\n').map(line => {
            // Remove up to 4 leading spaces
            if (line.startsWith('    ')) return line.substring(4);
            if (line.startsWith('\t')) return line.substring(1);
            if (line.startsWith(' ')) return line.replace(/^ {1,4}/, '');
            return line;
        }).join('\n');

        editor.value = value.substring(0, lineStart) + dedentedText + value.substring(actualEnd);

        // Adjust selection
        editor.selectionStart = lineStart;
        editor.selectionEnd = lineStart + dedentedText.length;
    }

    // Auto-close brackets and quotes
    const pairs = {
        '(': ')',
        '[': ']',
        '{': '}',
        '"': '"',
        "'": "'"
    };

    codeEditor.addEventListener('keypress', function (e) {
        const char = e.key;
        if (pairs[char]) {
            const start = this.selectionStart;
            const end = this.selectionEnd;
            const value = this.value;

            // Only auto-close if there's no selection or we're wrapping selection
            if (start === end || (char === '"' || char === "'")) {
                e.preventDefault();

                const selectedText = value.substring(start, end);
                const closing = pairs[char];

                // Insert opening, selected text, and closing
                const newValue = value.substring(0, start) + char + selectedText + closing + value.substring(end);
                this.value = newValue;

                // Position cursor
                if (selectedText) {
                    // If we wrapped text, select it
                    this.selectionStart = start + 1;
                    this.selectionEnd = end + 1;
                } else {
                    // Otherwise, put cursor between the pair
                    this.selectionStart = this.selectionEnd = start + 1;
                }
            }
        }
    });
});
