import React from 'react';

/**
 * NewItemsIndicator - Shows when new items are available
 * 
 * UX Rules:
 * - Never auto-loads items
 * - Never changes scroll position
 * - User clicks to load when ready
 */
const NewItemsIndicator = ({ count, onLoad }) => {
    if (count === 0) return null;

    return (
        <button
            onClick={onLoad}
            className="sticky top-0 w-full py-2 bg-blue-50 text-blue-600
                 text-sm font-medium border-b border-blue-100 z-10
                 hover:bg-blue-100 transition-colors"
        >
            {count} new item{count !== 1 ? 's' : ''} — Click to load
        </button>
    );
};

export default NewItemsIndicator;
