import React from 'react';

interface BoxProps {
  title: string;
  children: React.ReactNode;
}

const Box: React.FC<BoxProps> = ({ title, children }) => {
  return (
    <section className="w-full md:w-1/2">
      <h2 className="text-2xl font-semibold mb-4 text-blue-300">{title}</h2>
      <div className="bg-gray-800 rounded-lg p-4 h-[calc(100vh-200px)] overflow-y-auto border border-gray-700">
        {children}
      </div>
    </section>
  );
};

export default Box;

